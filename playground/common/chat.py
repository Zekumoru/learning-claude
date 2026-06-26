from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from typing import TypeVar, overload, cast
from collections.abc import Callable, Sequence
from pydantic import BaseModel
from anthropic import Anthropic, Omit, omit
from anthropic.types import (
    MessageParam,
    Message,
    ToolUnionParam,
    ToolResultBlockParam,
    ContentBlockParam,
    DocumentBlockParam,
    ThinkingConfigParam,
    TextBlockParam,
)
from anthropic.lib.streaming import (
    MessageStream,
    MessageStreamManager,
)
from .defaults import model, max_tokens
from .renderer import ConsoleWriter, MessageConsoleRenderer, StreamConsoleRenderer
from .usage_tracker import init_db, on_usage
import json

UsageCallback = Callable[[Message], None]

_usage_callbacks: list[UsageCallback] = [on_usage]


def register_usage_callback(cb: UsageCallback) -> None:
    _usage_callbacks.append(cb)


def _fire_usage_callbacks(message: Message) -> None:
    for cb in _usage_callbacks:
        cb(message)


client = Anthropic()
init_db()

TOmitValue = TypeVar("TOmitValue")


def omit_none(value: TOmitValue | None) -> TOmitValue | Omit:
    return omit if value is None else value


def add_user_message(
    messages: list[MessageParam], message: str | Message | Sequence[ContentBlockParam]
) -> None:
    messages.append(
        {
            "role": "user",
            "content": message.content if isinstance(message, Message) else message,
        }
    )


def add_assistant_message(messages: list[MessageParam], message: str | Message) -> None:
    messages.append(
        {
            "role": "assistant",
            "content": message.content if isinstance(message, Message) else message,
        }
    )


def text_from_message(message: Message) -> str:
    blocks = [block.text for block in message.content if block.type == "text"]
    return "\n".join(blocks)


TOutput = TypeVar("TOutput", bound=BaseModel)


def _with_cache_control(
    system: str | None,
    tools: list[ToolUnionParam] | None,
) -> tuple[list[TextBlockParam], list[ToolUnionParam] | None]:
    cached_system: list[TextBlockParam] = []
    cached_tools: list[ToolUnionParam] | None = tools

    if system:
        cached_system.append(
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        )

    if tools:
        cached_tools = [
            *tools[:-1],
            cast(ToolUnionParam, {**tools[-1], "cache_control": {"type": "ephemeral"}}),
        ]

    return cached_system, cached_tools


@overload
def chat(
    messages: list[MessageParam],
    *,
    system: str | None = None,
    temperature: float | None = None,
    stop_sequences: list[str] | None = None,
    tools: list[ToolUnionParam] | None = None,
    thinking: ThinkingConfigParam | None = None,
    caching: bool | None = None,
    output_format: None = None,
) -> Message: ...


@overload
def chat(
    messages: list[MessageParam],
    *,
    system: str | None = None,
    temperature: float | None = None,
    stop_sequences: list[str] | None = None,
    tools: list[ToolUnionParam] | None = None,
    thinking: ThinkingConfigParam | None = None,
    caching: bool | None = None,
    output_format: type[TOutput],
) -> TOutput: ...


def chat(
    messages: list[MessageParam],
    *,
    system: str | None = None,
    temperature: float | None = None,
    stop_sequences: list[str] | None = None,
    tools: list[ToolUnionParam] | None = None,
    thinking: ThinkingConfigParam | None = None,
    caching: bool | None = None,
    output_format: type[TOutput] | None = None,
) -> Message | TOutput:
    cached_system = None
    cached_tools = None

    if caching:
        cached_system, cached_tools = _with_cache_control(system, tools)

    if output_format is not None:
        response = client.messages.parse(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
            system=omit_none(cached_system or system),
            temperature=omit_none(temperature),
            stop_sequences=omit_none(stop_sequences),
            tools=omit_none(cached_tools or tools),
            thinking=omit_none(thinking),
            output_format=output_format,
        )

        parsed = response.parsed_output

        if not isinstance(parsed, output_format):
            raise TypeError(f"Expected parsed output of type {output_format.__name__}")

        return parsed

    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
        system=omit_none(cached_system or system),
        temperature=omit_none(temperature),
        stop_sequences=omit_none(stop_sequences),
        tools=omit_none(cached_tools or tools),
        thinking=omit_none(thinking),
    )

    _fire_usage_callbacks(message)
    return message


def chat_stream(
    messages: list[MessageParam],
    *,
    system: str | None = None,
    temperature: float | None = None,
    stop_sequences: list[str] | None = None,
    thinking: ThinkingConfigParam | None = None,
    tools: list[ToolUnionParam] | None = None,
    caching: bool | None = None,
) -> MessageStreamManager[None]:
    cached_system = None
    cached_tools = None

    if caching:
        cached_system, cached_tools = _with_cache_control(system, tools)

    return client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
        system=omit_none(cached_system or system),
        temperature=omit_none(temperature),
        stop_sequences=omit_none(stop_sequences),
        tools=omit_none(cached_tools or tools),
        thinking=omit_none(thinking),
    )


def _has_document_blocks(blocks: list[object]) -> bool:
    return any(isinstance(b, dict) and b.get("type") == "document" for b in blocks)


def run_tools(
    message: Message, run_tool: Callable[[str, dict[str, object]], object] | None
) -> tuple[list[ToolResultBlockParam], list[DocumentBlockParam]]:
    tool_requests = [block for block in message.content if block.type == "tool_use"]
    tool_result_blocks: list[ToolResultBlockParam] = []
    document_blocks: list[DocumentBlockParam] = []

    for tool_request in tool_requests:
        try:
            if run_tool is None:
                raise ValueError(
                    f"Could not run tool '{tool_request.name}': missing tool handler."
                )

            tool_output = run_tool(tool_request.name, tool_request.input)

            if isinstance(tool_output, list) and _has_document_blocks(tool_output):
                for block in tool_output:
                    document_blocks.append(cast(DocumentBlockParam, block))
                tool_result_block: ToolResultBlockParam = {
                    "type": "tool_result",
                    "tool_use_id": tool_request.id,
                    "content": "Document loaded successfully.",
                    "is_error": False,
                }
            else:
                tool_result_block = {
                    "type": "tool_result",
                    "tool_use_id": tool_request.id,
                    "content": (
                        tool_output
                        if isinstance(tool_output, list)
                        else json.dumps(tool_output)
                    ),
                    "is_error": False,
                }
        except Exception as e:
            tool_result_block = {
                "type": "tool_result",
                "tool_use_id": tool_request.id,
                "content": f"Error: {e}",
                "is_error": True,
            }

        tool_result_blocks.append(tool_result_block)

    return tool_result_blocks, document_blocks


def run_conversation(
    messages: list[MessageParam],
    tools: list[ToolUnionParam] | None = None,
    run_tool_callback: Callable[[str, dict[str, object]], object] | None = None,
    thinking: ThinkingConfigParam | None = None,
    caching: bool | None = None,
    verbose: bool = False,
) -> None:
    renderer = MessageConsoleRenderer()

    while True:
        response = chat(messages, tools=tools, thinking=thinking, caching=caching)

        if verbose:
            renderer.verbose_json(response)

        add_assistant_message(messages, response)
        renderer.message(response)

        if response.stop_reason == "max_tokens":
            renderer.max_tokens_error()

        if response.stop_reason != "tool_use":
            break

        tool_results, documents = run_tools(response, run_tool_callback)

        if verbose:
            renderer.verbose_json(tool_results)

        add_user_message(messages, [*tool_results, *documents])


def _handle_stream_event(
    stream: MessageStream[None],
    tools: list[ToolUnionParam] | None = None,
    writer: ConsoleWriter | None = None,
) -> StreamConsoleRenderer:
    renderer = StreamConsoleRenderer(tools=tools, writer=writer)
    renderer.render(stream)
    return renderer


def run_conversation_stream(
    messages: list[MessageParam],
    system: str | None = None,
    tools: list[ToolUnionParam] | None = None,
    run_tool_callback: Callable[[str, dict[str, object]], object] | None = None,
    thinking: ThinkingConfigParam | None = None,
    caching: bool | None = None,
    verbose: bool = False,
) -> None:
    writer = ConsoleWriter()
    message_renderer = MessageConsoleRenderer(writer)

    while True:
        with chat_stream(
            messages, system=system, tools=tools, thinking=thinking, caching=caching
        ) as stream:
            stream_renderer = _handle_stream_event(stream, tools=tools, writer=writer)
            response = stream.get_final_message()

        is_tool_use = response.stop_reason in ("tool_use", "pause_turn")

        if not is_tool_use:
            stream_renderer.finish_inline_output()

        if verbose:
            message_renderer.verbose_json(response)

        add_assistant_message(messages, response)
        message_renderer.usage(response)
        _fire_usage_callbacks(response)

        if response.stop_reason == "max_tokens":
            message_renderer.max_tokens_error()

        if not is_tool_use:
            break

        writer.gap(1)

        if response.stop_reason == "pause_turn":
            messages = [
                messages[0],
                {"role": "assistant", "content": response.content},
            ]
            continue

        tool_results, documents = run_tools(response, run_tool_callback)

        if verbose:
            message_renderer.verbose_json(tool_results)

        add_user_message(messages, [*tool_results, *documents])
