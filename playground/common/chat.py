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
    BetaMessageStream,
    BetaMessageStreamManager,
)
from anthropic.types.beta import (
    BetaMessage,
    BetaMessageParam,
    BetaTextBlockParam,
    BetaToolUnionParam,
    BetaThinkingConfigParam,
    BetaContainerUploadBlockParam,
)
from .types import AnyMessage
from .defaults import model, max_tokens
from .renderer import ConsoleWriter, MessageConsoleRenderer, StreamConsoleRenderer
from .usage_tracker import init_db, on_usage
import json

UsageCallback = Callable[[AnyMessage], None]

_usage_callbacks: list[UsageCallback] = [on_usage]


def register_usage_callback(cb: UsageCallback) -> None:
    _usage_callbacks.append(cb)


def _fire_usage_callbacks(message: AnyMessage) -> None:
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


def add_assistant_message(
    messages: list[MessageParam], message: str | AnyMessage
) -> None:
    content: str | list[ContentBlockParam] = (
        message
        if isinstance(message, str)
        else cast(list[ContentBlockParam], message.content)
    )
    messages.append({"role": "assistant", "content": content})


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


def _with_message_cache_control(messages: list[MessageParam]) -> list[MessageParam]:
    """Return a copy of `messages` with a cache breakpoint on the last block of
    the last message.

    A breakpoint on a message caches the entire prefix before it — tools, system,
    and the conversation so far — so a long, growing history is read from cache on
    the next turn instead of being reprocessed at full price. This "moving"
    breakpoint walks forward each turn as new messages are appended.

    Non-mutating: the caller's list and message dicts are left untouched, so
    markers never accumulate across turns (each request carries exactly one).
    """
    if not messages:
        return messages

    last = messages[-1]
    content = last["content"]

    if isinstance(content, str):
        marked: list[ContentBlockParam] = [
            {"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}
        ]
    else:
        # The last message at a stream call is always a user message (initial
        # text or tool results), so its content blocks are param dicts, not
        # response ContentBlock models.
        blocks = cast(list[ContentBlockParam], list(content))
        if not blocks:
            return messages
        marked = [
            *blocks[:-1],
            cast(
                ContentBlockParam,
                {**blocks[-1], "cache_control": {"type": "ephemeral"}},
            ),
        ]

    return [*messages[:-1], {"role": last["role"], "content": marked}]


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
    betas: list[str] | None = None,
    container: str | None = None,
) -> MessageStreamManager[None] | BetaMessageStreamManager[None]:
    cached_system = None
    cached_tools = None
    cached_messages = messages

    if caching:
        cached_system, cached_tools = _with_cache_control(system, tools)
        # Moving breakpoint on the latest message — caches tools + system + the
        # whole conversation prefix so the growing history is read from cache.
        cached_messages = _with_message_cache_control(messages)

    if betas:
        return client.beta.messages.stream(
            model=model,
            max_tokens=max_tokens,
            messages=cast(list[BetaMessageParam], cached_messages),
            system=omit_none(
                cast(list[BetaTextBlockParam] | str | None, cached_system or system)
            ),
            temperature=omit_none(temperature),
            stop_sequences=omit_none(stop_sequences),
            tools=omit_none(
                cast(list[BetaToolUnionParam] | None, cached_tools or tools)
            ),
            thinking=omit_none(cast(BetaThinkingConfigParam | None, thinking)),
            container=omit_none(container),
            betas=betas,
        )

    return client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        messages=cached_messages,
        system=omit_none(cached_system or system),
        temperature=omit_none(temperature),
        stop_sequences=omit_none(stop_sequences),
        tools=omit_none(cached_tools or tools),
        thinking=omit_none(thinking),
    )


# Block types that must be hoisted out of a tool_result and into the user
# message itself: `document` (for citations) and `container_upload` (for the
# code-execution container). Neither is valid nested inside a tool_result.
HOISTED_BLOCK_TYPES = {"document", "container_upload"}


def _hoisted_blocks(tool_output: object) -> list[dict[str, object]]:
    if not isinstance(tool_output, list):
        return []
    return [
        block
        for block in tool_output
        if isinstance(block, dict) and block.get("type") in HOISTED_BLOCK_TYPES
    ]


def run_tools(
    message: AnyMessage, run_tool: Callable[[str, dict[str, object]], object] | None
) -> tuple[
    list[ToolResultBlockParam],
    list[DocumentBlockParam],
    list[BetaContainerUploadBlockParam],
]:
    tool_requests = [block for block in message.content if block.type == "tool_use"]
    tool_result_blocks: list[ToolResultBlockParam] = []
    document_blocks: list[DocumentBlockParam] = []
    container_upload_blocks: list[BetaContainerUploadBlockParam] = []

    for tool_request in tool_requests:
        try:
            if run_tool is None:
                raise ValueError(
                    f"Could not run tool '{tool_request.name}': missing tool handler."
                )

            tool_output = run_tool(tool_request.name, tool_request.input)
            hoisted = _hoisted_blocks(tool_output)

            if hoisted:
                for block in hoisted:
                    match block.get("type"):
                        case "document":
                            document_blocks.append(cast(DocumentBlockParam, block))
                        case "container_upload":
                            container_upload_blocks.append(
                                cast(BetaContainerUploadBlockParam, block)
                            )
                tool_result_block: ToolResultBlockParam = {
                    "type": "tool_result",
                    "tool_use_id": tool_request.id,
                    "content": "Loaded successfully.",
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

    return tool_result_blocks, document_blocks, container_upload_blocks


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

        tool_results, documents, _ = run_tools(response, run_tool_callback)

        if verbose:
            renderer.verbose_json(tool_results)

        add_user_message(messages, [*tool_results, *documents])


def _handle_stream_event(
    stream: MessageStream[None] | BetaMessageStream[None],
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
    betas: list[str] | None = None,
    on_response: Callable[[AnyMessage], None] | None = None,
    verbose: bool = False,
) -> None:
    writer = ConsoleWriter()
    message_renderer = MessageConsoleRenderer(writer)
    container_id: str | None = None

    while True:
        with chat_stream(
            messages,
            system=system,
            tools=tools,
            thinking=thinking,
            caching=caching,
            betas=betas,
            container=container_id,
        ) as stream:
            stream_renderer = _handle_stream_event(stream, tools=tools, writer=writer)
            response = stream.get_final_message()

        # Persist the code-execution container across turns so a paused turn
        # (pause_turn) resumes the same container instead of orphaning its
        # server tool use with a fresh one.
        if isinstance(response, BetaMessage) and response.container is not None:
            container_id = response.container.id

        is_tool_use = response.stop_reason in ("tool_use", "pause_turn")

        if not is_tool_use:
            stream_renderer.finish_inline_output()

        if verbose:
            message_renderer.verbose_json(response)

        add_assistant_message(messages, response)
        message_renderer.usage(response)
        _fire_usage_callbacks(response)

        if on_response is not None:
            on_response(response)

        if response.stop_reason == "max_tokens":
            message_renderer.max_tokens_error()

        if not is_tool_use:
            break

        writer.gap(1)

        if response.stop_reason == "pause_turn":
            continue

        tool_results, documents, container_uploads = run_tools(
            response, run_tool_callback
        )

        if verbose:
            message_renderer.verbose_json(tool_results)

        add_user_message(
            messages,
            [
                *tool_results,
                *documents,
                # container_upload is a beta-only block; it round-trips as a dict
                # and the beta endpoint consumes it, so we cast at this boundary.
                *cast(list[ContentBlockParam], container_uploads),
            ],
        )
