from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from typing import Protocol, TypeGuard, TypeVar, overload, cast, Mapping
from collections.abc import Callable, Sequence
from pydantic import BaseModel
from anthropic import Anthropic, Omit, omit
from anthropic.types import (
    ModelParam,
    MessageParam,
    Message,
    ToolUnionParam,
    ToolResultBlockParam,
    ContentBlockParam,
    DocumentBlockParam,
    ThinkingConfigParam,
    ContentBlock,
    RawContentBlockDelta,
    RawContentBlockStartEvent,
    RawContentBlockDeltaEvent,
    RawContentBlockStopEvent,
    ServerToolUseBlock,
    ToolUseBlock,
    ThinkingBlock,
    RedactedThinkingBlock,
    TextBlock,
    TextDelta,
    InputJSONDelta,
    ThinkingDelta,
    CitationsDelta,
    SignatureDelta,
    TextCitation,
    CitationPageLocation,
    CitationCharLocation,
)
from anthropic.lib.streaming import (
    MessageStream,
    MessageStreamManager,
    ParsedMessageStreamEvent,
)
import json

model: ModelParam = "claude-sonnet-4-6"
max_tokens = 4096

PRICING_PER_MILLION: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-8": {"input": 5.00, "output": 25.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}

client = Anthropic()


RESET = "\033[0m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
CYAN = "\033[36m"
RED = "\033[31m"
MAGENTA = "\033[35m"


def color(text: str, ansi_color: str) -> str:
    return f"{ansi_color}{text}{RESET}"


class SupportsModelDumpJson(Protocol):
    def model_dump_json(self, *, indent: int | None = None) -> str: ...


def supports_model_dump_json(value: object) -> TypeGuard[SupportsModelDumpJson]:
    return hasattr(value, "model_dump_json")


TOmitValue = TypeVar("TOmitValue")


def omit_none(value: TOmitValue | None) -> TOmitValue | Omit:
    return omit if value is None else value


class ConsoleWriter:
    """Small terminal-layout helper.

    The important idea is that call sites should say *what* they are printing
    (line, heading, streamed text), while this class decides how to keep the
    terminal output readable.
    """

    def __init__(self) -> None:
        self._has_written = False
        self._line_open = False

    def write(self, text: str) -> None:
        if not text:
            return

        print(text, end="", flush=True)
        self._has_written = True
        self._line_open = not text.endswith("\n")

    def newline(self, count: int = 1) -> None:
        for _ in range(count):
            print(flush=True)

        if count > 0:
            self._has_written = True
            self._line_open = False

    def gap(self, blank_lines: int = 1, *, include_initial: bool = True) -> None:
        """Move to the next section with a controlled number of blank lines.

        `blank_lines=1` means "leave one visual blank line before the next
        section". If streamed text is currently open, the first newline closes
        that line and the extra newline creates the visual gap.
        """

        if blank_lines < 0:
            raise ValueError("blank_lines must be >= 0")

        if not self._has_written:
            if include_initial and blank_lines > 0:
                self.newline(blank_lines)
            return

        if self._line_open:
            self.newline()

        self.newline(blank_lines)

    def line(
        self,
        text: str = "",
        *,
        before: int = 0,
        include_initial_gap: bool = True,
    ) -> None:
        self.gap(before, include_initial=include_initial_gap)
        print(text, flush=True)
        self._has_written = True
        self._line_open = False

    def heading(
        self,
        label: str,
        ansi_color: str,
        *,
        before: int = 1,
        include_initial_gap: bool = True,
    ) -> None:
        self.line(
            color(label, ansi_color),
            before=before,
            include_initial_gap=include_initial_gap,
        )


def print_citations(citations: list[TextCitation], writer: ConsoleWriter) -> None:
    if not citations:
        return

    writer.line(color("--- References ---", YELLOW), before=1)

    for i, citation in enumerate(citations, 1):
        cited_text = " ".join(citation.cited_text.split())[:80]

        if len(citation.cited_text) > 80:
            cited_text += "..."

        match citation:
            case CitationPageLocation():
                pages = f"p.{citation.start_page_number}"
                if citation.end_page_number != citation.start_page_number:
                    pages = f"p.{citation.start_page_number}-{citation.end_page_number}"
                writer.line(f'[{i}] ({pages}) "{cited_text}"')
            case CitationCharLocation():
                writer.line(
                    f"[{i}] (char {citation.start_char_index}-{citation.end_char_index})"
                    f' "{cited_text}."'
                )


class MessageConsoleRenderer:
    def __init__(self, writer: ConsoleWriter | None = None) -> None:
        self.writer = writer or ConsoleWriter()

    def verbose_json(self, value: object) -> None:
        if supports_model_dump_json(value):
            rendered = value.model_dump_json(indent=2)
        else:
            rendered = json.dumps(value, indent=2)

        self.writer.line(rendered)
        self.writer.newline()

    def usage(self, message: Message, *, before: int = 1) -> None:
        self.writer.line(format_usage(message), before=before)

    def max_tokens_error(self) -> None:
        self.writer.line("Error: max_tokens reached")
        self.writer.newline()

    def message(self, message: Message) -> None:
        self.usage(message)

        has_thinking = any(
            isinstance(block, (ThinkingBlock, RedactedThinkingBlock))
            for block in message.content
        )

        citations: list[TextCitation] = []
        printed_response_heading = False

        for block in message.content:
            match block:
                case ThinkingBlock():
                    self.writer.heading("[Thinking]", CYAN)
                    self.writer.line(block.thinking)
                case RedactedThinkingBlock():
                    self.writer.heading("[Redacted]", RED)
                    self.writer.line(f"(encrypted, {len(block.data)} chars)")
                case TextBlock():
                    if not block.text.strip():
                        continue

                    if has_thinking and not printed_response_heading:
                        self.writer.heading("[Response]", GREEN)
                        printed_response_heading = True

                    if not has_thinking and not printed_response_heading:
                        self.writer.gap(1)
                        printed_response_heading = True

                    if block.citations:
                        for citation in block.citations:
                            if citation not in citations:
                                citations.append(citation)
                            index = citations.index(citation) + 1
                            block.text += f"[{index}]"

                    self.writer.write(block.text)

        print_citations(citations, self.writer)


class StreamConsoleRenderer:
    def __init__(
        self,
        tools: list[ToolUnionParam] | None = None,
        writer: ConsoleWriter | None = None,
    ) -> None:
        self.writer = writer or ConsoleWriter()
        self.tool_inputs: dict[int, str] = {}
        self.eager_indices: set[int] = set()
        self.printed_text = False
        self.printed_thinking = False
        self.eager_by_tool_name = _get_eager_input_streaming_by_tool_name(tools)
        self.citations: list[TextCitation] = []

    def render(self, stream: MessageStream[None]) -> None:
        for event in stream:
            self.handle(event)

    def handle(self, event: ParsedMessageStreamEvent[None]) -> None:
        match event:
            case RawContentBlockStartEvent():
                self._handle_content_block_start(event.index, event.content_block)
            case RawContentBlockDeltaEvent():
                self._handle_content_block_delta(event.index, event.delta)
            case RawContentBlockStopEvent():
                self._handle_content_block_stop(event.index)

    def finish_inline_output(self) -> None:
        self.writer.gap(0)
        print_citations(self.citations, self.writer)

    def _handle_content_block_start(
        self, index: int, content_block: ContentBlock
    ) -> None:
        match content_block:
            case ServerToolUseBlock():
                self._status("Searching the web...", MAGENTA)
            case ToolUseBlock():
                self._start_tool_use(index, content_block.name)
            case ThinkingBlock():
                self.printed_thinking = True
                self.writer.heading("[Thinking]", CYAN)
            case TextBlock():
                if self.printed_thinking and not self.printed_text:
                    self.writer.heading("[Response]", GREEN)

    def _handle_content_block_delta(
        self, index: int, delta: RawContentBlockDelta
    ) -> None:
        match delta:
            case TextDelta():
                self.printed_text = True
                self.writer.write(delta.text)
            case InputJSONDelta():
                self._append_tool_input(index, delta.partial_json)
            case ThinkingDelta():
                self.writer.write(delta.thinking)
            case CitationsDelta():
                citation = delta.citation
                if citation not in self.citations:
                    self.citations.append(citation)
                citation_index = self.citations.index(citation) + 1
                self.writer.write(f"[{citation_index}]")
            case SignatureDelta():
                return

    def _handle_content_block_stop(self, index: int) -> None:
        if index not in self.tool_inputs:
            return

        raw_input = self.tool_inputs[index]
        if not raw_input:
            return

        try:
            json.loads(raw_input)
        except json.JSONDecodeError:
            self.writer.line("Error: Received invalid JSON after stream", before=1)

    def _start_tool_use(self, index: int, tool_name: str) -> None:
        self.tool_inputs[index] = ""

        if self.eager_by_tool_name.get(tool_name, False):
            self.eager_indices.add(index)
            self._status(f"Generating tool use `{tool_name}` arguments...", CYAN)
        else:
            self._status(f"Using tool `{tool_name}`...", CYAN)

    def _append_tool_input(self, index: int, partial_json: str) -> None:
        if index not in self.tool_inputs:
            return

        self.tool_inputs[index] += partial_json

        if index in self.eager_indices:
            self.writer.write(partial_json)

    def _status(self, message: str, ansi_color: str) -> None:
        self.writer.line(
            color(message, ansi_color), before=1 if self.printed_text else 0
        )


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


def format_usage(message: Message) -> str:
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

    return color(
        f"[{input_tokens} in + {output_tokens} out = {total_tokens} tokens{cost_str}]",
        YELLOW,
    )


def print_usage(message: Message) -> None:
    print(format_usage(message))


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
    if output_format is not None:
        response = client.messages.parse(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
            system=omit_none(system),
            temperature=omit_none(temperature),
            stop_sequences=omit_none(stop_sequences),
            tools=omit_none(tools),
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
        system=omit_none(system),
        temperature=omit_none(temperature),
        stop_sequences=omit_none(stop_sequences),
        tools=omit_none(tools),
        thinking=omit_none(thinking),
    )

    return cast(Message, message)


def chat_stream(
    messages: list[MessageParam],
    *,
    system: str | None = None,
    temperature: float | None = None,
    stop_sequences: list[str] | None = None,
    thinking: ThinkingConfigParam | None = None,
    tools: list[ToolUnionParam] | None = None,
) -> MessageStreamManager[None]:
    return client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
        system=omit_none(system),
        temperature=omit_none(temperature),
        stop_sequences=omit_none(stop_sequences),
        tools=omit_none(tools),
        thinking=omit_none(thinking),
    )


def _has_document_blocks(blocks: list[object]) -> bool:
    return any(
        isinstance(b, dict) and b.get("type") == "document"
        for b in blocks
    )


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
    verbose: bool = False,
) -> None:
    renderer = MessageConsoleRenderer()

    while True:
        response = chat(messages, tools=tools, thinking=thinking)

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
    verbose: bool = False,
) -> None:
    writer = ConsoleWriter()
    message_renderer = MessageConsoleRenderer(writer)

    while True:
        with chat_stream(
            messages, system=system, tools=tools, thinking=thinking
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
