from dotenv import load_dotenv

load_dotenv()

from typing import TypeVar, overload, cast, Any, Mapping
from collections.abc import Callable
from pydantic import BaseModel
from anthropic import Anthropic
from anthropic.types import (
    ModelParam,
    MessageParam,
    MessageCreateParams,
    Message,
    ToolUnionParam,
    ToolResultBlockParam,
    ThinkingConfigParam,
)
from anthropic.lib.streaming import MessageStream, MessageStreamManager
import json

model: ModelParam = "claude-sonnet-4-6"
max_tokens = 4096

PRICING_PER_MILLION: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-8": {"input": 5.00, "output": 25.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}

client = Anthropic()


def add_user_message(
    messages: list[MessageParam], message: str | Message | list[ToolResultBlockParam]
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


def print_usage(message: Message) -> None:
    usage = message.usage
    input_tokens = usage.input_tokens
    output_tokens = usage.output_tokens
    total_tokens = input_tokens + output_tokens

    pricing = PRICING_PER_MILLION.get(model)

    if pricing:
        input_cost = input_tokens * pricing["input"] / 1_000_000
        output_cost = output_tokens * pricing["output"] / 1_000_000
        total_cost = input_cost + output_cost
        cost_str = f" | ${total_cost:.6f}"
    else:
        cost_str = ""

    print(
        f"\033[33m[{input_tokens} in + {output_tokens} out = {total_tokens} tokens{cost_str}]\033[0m"
    )


TOutput = TypeVar("TOutput", bound=BaseModel)


@overload
def chat(
    messages: list[MessageParam],
    *,
    system: str | None = None,
    temperature: float | None = None,
    stop_sequences: list[str] | None = None,
    tools: list[ToolUnionParam] | None = None,
    thinking: ThinkingConfigParam | None = None,
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
    output_format: type[TOutput] | None = None,
) -> Message | TOutput:
    params: MessageCreateParams = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }

    if system is not None:
        params["system"] = system

    if temperature is not None:
        params["temperature"] = temperature

    if stop_sequences is not None:
        params["stop_sequences"] = stop_sequences

    if tools is not None:
        params["tools"] = tools

    if thinking is not None:
        params["thinking"] = thinking

    if output_format is not None:
        response = client.messages.parse(
            **cast(Any, params), output_format=output_format
        )

        parsed = response.parsed_output

        if not isinstance(parsed, output_format):
            raise TypeError(f"Expected parsed output of type {output_format.__name__}")

        return parsed

    message = client.messages.create(**params)
    return message


def chat_stream(
    messages: list[MessageParam],
    *,
    system: str | None = None,
    temperature: float | None = None,
    stop_sequences: list[str] | None = None,
    tools: list[ToolUnionParam] | None = None,
) -> MessageStreamManager:
    params: MessageCreateParams = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }

    if system is not None:
        params["system"] = system

    if temperature is not None:
        params["temperature"] = temperature

    if stop_sequences is not None:
        params["stop_sequences"] = stop_sequences

    if tools is not None:
        params["tools"] = tools

    return client.messages.stream(**cast(Any, params))


def run_tools(
    message: Message, run_tool: Callable[[str, dict[str, Any]], Any] | None
) -> list[ToolResultBlockParam]:
    tool_requests = [block for block in message.content if block.type == "tool_use"]
    tool_result_blocks: list[ToolResultBlockParam] = []

    for tool_request in tool_requests:
        try:
            if run_tool is None:
                raise ValueError(
                    f"Could not run tool '{tool_request.name}': missing tool handler."
                )

            tool_output = run_tool(tool_request.name, tool_request.input)
            tool_result_block: ToolResultBlockParam = {
                "type": "tool_result",
                "tool_use_id": tool_request.id,
                "content": json.dumps(tool_output),
                "is_error": False,
            }
        except Exception as e:
            tool_result_block: ToolResultBlockParam = {
                "type": "tool_result",
                "tool_use_id": tool_request.id,
                "content": f"Error: {e}",
                "is_error": True,
            }

        tool_result_blocks.append(tool_result_block)

    return tool_result_blocks


def run_conversation(
    messages: list[MessageParam],
    tools: list[ToolUnionParam] | None = None,
    run_tool_callback: Callable[[str, dict[str, Any]], Any] | None = None,
    verbose: bool = False,
) -> None:
    while True:
        response = chat(messages, tools=tools)
        if verbose:
            print(response.model_dump_json(indent=2) + "\n")

        add_assistant_message(messages, response)
        print_usage(response)
        print("\n")

        text = text_from_message(response)

        if text.strip() != "":
            print(text + "\n")

        if response.stop_reason == "max_tokens":
            print("Error: max_tokens reached\n")

        if response.stop_reason != "tool_use":
            break

        tool_results = run_tools(response, run_tool_callback)
        if verbose:
            print(json.dumps(tool_results, indent=2) + "\n")
        add_user_message(messages, tool_results)

    return


def _get_eager_input_streaming_by_tool_name(
    tools: list[ToolUnionParam] | None,
) -> dict[str, bool]:
    result: dict[str, bool] = {}

    for tool in tools or []:
        tool_dict = cast(Mapping[str, object], tool)

        name = tool_dict.get("name")
        if not isinstance(name, str):
            continue

        result[name] = tool_dict.get("eager_input_streaming") is True

    return result


def _handle_stream_event(
    stream: MessageStream[Any],
    tools: list[ToolUnionParam] | None = None,
) -> None:
    tool_inputs: dict[int, str] = {}
    eager_indices: set[int] = set()
    printed_text = False
    eager_by_tool_name = _get_eager_input_streaming_by_tool_name(tools)

    for event in stream:
        match event.type:
            case "content_block_start":
                if event.content_block.type == "server_tool_use":
                    prefix = "\n" if printed_text else ""
                    print(f"{prefix}\033[35mSearching the web...\033[0m", flush=True)
                elif event.content_block.type == "tool_use":
                    tool_inputs[event.index] = ""
                    tool_name = event.content_block.name
                    prefix = "\n" if printed_text else ""
                    if eager_by_tool_name.get(tool_name, False):
                        eager_indices.add(event.index)
                        print(
                            f"{prefix}\033[36mGenerating tool use `{tool_name}` arguments...\033[0m\n",
                            end="",
                            flush=True,
                        )
                    else:
                        print(
                            f"{prefix}\033[36mUsing tool `{tool_name}`...\033[0m",
                            flush=True,
                        )
            case "content_block_delta":
                if event.delta.type == "text_delta":
                    printed_text = True
                    print(event.delta.text, end="", flush=True)
                elif event.delta.type == "input_json_delta":
                    if event.index in tool_inputs:
                        tool_inputs[event.index] += event.delta.partial_json
                        if event.index in eager_indices:
                            print(event.delta.partial_json, end="", flush=True)
            case "content_block_stop":
                if event.index in tool_inputs:
                    raw_input = tool_inputs[event.index]
                    try:
                        if raw_input:
                            json.loads(raw_input)
                    except json.JSONDecodeError:
                        print("Error: Received invalid JSON after stream")


def run_conversation_stream(
    messages: list[MessageParam],
    system: str | None = None,
    tools: list[ToolUnionParam] | None = None,
    run_tool_callback: Callable[[str, dict[str, Any]], Any] | None = None,
    verbose: bool = False,
) -> None:
    while True:
        with chat_stream(messages, system=system, tools=tools) as stream:
            _handle_stream_event(stream, tools=tools)

            response = stream.get_final_message()

        is_tool_use = response.stop_reason in ("tool_use", "pause_turn")

        if not is_tool_use:
            print("\n")
        else:
            print()

        if verbose:
            print(response.model_dump_json(indent=2) + "\n")

        add_assistant_message(messages, response)
        print_usage(response)
        print("\n")

        if response.stop_reason == "max_tokens":
            print("Error: max_tokens reached\n")

        if not is_tool_use:
            break

        if response.stop_reason == "pause_turn":
            messages = [
                messages[0],
                {"role": "assistant", "content": response.content},
            ]
            continue

        tool_results = run_tools(response, run_tool_callback)

        if verbose:
            print(json.dumps(tool_results, indent=2) + "\n")

        add_user_message(messages, tool_results)
