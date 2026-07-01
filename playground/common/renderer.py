from anthropic.types import (
    Message,
    ToolUnionParam,
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
    Usage,
    ModelParam,
)
from anthropic.lib.streaming import (
    MessageStream,
    ParsedMessageStreamEvent,
    BetaMessageStream,
    ParsedBetaMessageStreamEvent,
)
from anthropic.types.beta import (
    BetaContentBlock,
    BetaRawContentBlockDelta,
    BetaRawContentBlockStartEvent,
    BetaRawContentBlockDeltaEvent,
    BetaRawContentBlockStopEvent,
    BetaServerToolUseBlock,
    BetaToolUseBlock,
    BetaThinkingBlock,
    BetaTextBlock,
    BetaTextDelta,
    BetaInputJSONDelta,
    BetaThinkingDelta,
    BetaSignatureDelta,
    BetaUsage,
)
from .types import AnyMessage
from typing import Protocol, TypeGuard, Literal, cast, Mapping, Any
from .pricing import pricing_for
import json

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


def format_usage(
    model: ModelParam,
    usage: Usage | BetaUsage | dict[str, Any],
    cost: float | None = None,  # if cost is already known
) -> str:
    if isinstance(usage, dict):
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cache_creation = usage.get("cache_creation_input_tokens", 0)
        cache_read = usage.get("cache_read_input_tokens", 0)
    else:
        input_tokens = usage.input_tokens
        output_tokens = usage.output_tokens
        cache_creation = usage.cache_creation_input_tokens or 0
        cache_read = usage.cache_read_input_tokens or 0

    total_tokens = input_tokens + cache_creation + cache_read + output_tokens
    total_cost = cost or -1

    if cost is None:
        pricing = pricing_for(model)

        if pricing:
            rate = pricing["input"] / 1_000_000
            input_cost = input_tokens * rate
            output_cost = output_tokens * pricing["output"] / 1_000_000
            cache_creation_cost = cache_creation * rate * 1.25
            cache_read_cost = cache_read * rate * 0.1
            total_cost = (
                input_cost + output_cost + cache_creation_cost + cache_read_cost
            )

    cost_str = f" (${total_cost:.6f})" if total_cost >= 0 else ""

    parts = [f"{input_tokens} in", f"{output_tokens} out"]
    if cache_creation:
        parts.append(f"{cache_creation} cache write")
    if cache_read:
        parts.append(f"{cache_read} cache read")

    return color(
        f"[{' + '.join(parts)} = {total_tokens} tokens{cost_str}]",
        YELLOW,
    )


def print_usage(message: Message) -> None:
    print(format_usage(message.model, message.usage))


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

    def usage(self, message: AnyMessage, *, before: int = 1) -> None:
        self.writer.line(format_usage(message.model, message.usage), before=before)

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


def _server_tool_status(tool_name: str) -> str:
    match tool_name:
        case "web_search":
            return "Searching the web..."
        case "bash_code_execution":
            return "Running code..."
        case "text_editor_code_execution":
            return "Editing files..."
        case _:
            return f"Using {tool_name}..."


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


# The kind of output segment last rendered within a turn. Drives both section
# headings and the blank-line spacing between segments.
Section = Literal["none", "thinking", "text", "status"]


class StreamConsoleRenderer:
    def __init__(
        self,
        tools: list[ToolUnionParam] | None = None,
        writer: ConsoleWriter | None = None,
    ) -> None:
        self.writer = writer or ConsoleWriter()
        self.tool_inputs: dict[int, str] = {}
        self.eager_indices: set[int] = set()
        self.section: Section = "none"
        self.eager_by_tool_name = _get_eager_input_streaming_by_tool_name(tools)
        self.citations: list[TextCitation] = []

    def render(self, stream: MessageStream[None] | BetaMessageStream[None]) -> None:
        for event in stream:
            self.handle(event)

    def handle(
        self, event: ParsedMessageStreamEvent[None] | ParsedBetaMessageStreamEvent[None]
    ) -> None:
        match event:
            case RawContentBlockStartEvent() | BetaRawContentBlockStartEvent():
                self._handle_content_block_start(event.index, event.content_block)
            case RawContentBlockDeltaEvent() | BetaRawContentBlockDeltaEvent():
                self._handle_content_block_delta(event.index, event.delta)
            case RawContentBlockStopEvent() | BetaRawContentBlockStopEvent():
                self._handle_content_block_stop(event.index)

    def finish_inline_output(self) -> None:
        self.writer.gap(0)
        print_citations(self.citations, self.writer)

    def _handle_content_block_start(
        self, index: int, content_block: ContentBlock | BetaContentBlock
    ) -> None:
        # One blank line before each new segment, except the first of the turn —
        # there the gap between turns (or nothing, for turn one) already spaces it.
        before = 0 if self.section == "none" else 1

        match content_block:
            case ServerToolUseBlock() | BetaServerToolUseBlock():
                self._status(_server_tool_status(content_block.name), MAGENTA, before)
                self.section = "status"
            case ToolUseBlock() | BetaToolUseBlock():
                self._start_tool_use(index, content_block.name, before)
                self.section = "status"
            case ThinkingBlock() | BetaThinkingBlock():
                self.writer.heading("[Thinking]", CYAN, before=before)
                self.section = "thinking"
            case TextBlock() | BetaTextBlock():
                # Only label the response when it resumes after thinking or a
                # tool; a plain answer with no preamble needs no heading.
                if self.section in ("thinking", "status"):
                    self.writer.heading("[Response]", GREEN, before=before)
                self.section = "text"

    def _handle_content_block_delta(
        self, index: int, delta: RawContentBlockDelta | BetaRawContentBlockDelta
    ) -> None:
        match delta:
            case TextDelta() | BetaTextDelta():
                self.writer.write(delta.text)
            case InputJSONDelta() | BetaInputJSONDelta():
                self._append_tool_input(index, delta.partial_json)
            case ThinkingDelta() | BetaThinkingDelta():
                self.writer.write(delta.thinking)
            # Regular-only: the beta stream path is used for code execution /
            # Files API, which never emits citations. Matching BetaCitationsDelta
            # here would force self.citations and print_citations to widen into
            # beta location types for no real gain.
            case CitationsDelta():
                citation = delta.citation
                if citation not in self.citations:
                    self.citations.append(citation)
                citation_index = self.citations.index(citation) + 1
                self.writer.write(f"[{citation_index}]")
            case SignatureDelta() | BetaSignatureDelta():
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

    def _start_tool_use(self, index: int, tool_name: str, before: int) -> None:
        self.tool_inputs[index] = ""

        if self.eager_by_tool_name.get(tool_name, False):
            self.eager_indices.add(index)
            self._status(
                f"Generating tool use `{tool_name}` arguments...", CYAN, before
            )
        else:
            self._status(f"Using tool `{tool_name}`...", CYAN, before)

    def _append_tool_input(self, index: int, partial_json: str) -> None:
        if index not in self.tool_inputs:
            return

        self.tool_inputs[index] += partial_json

        if index in self.eager_indices:
            self.writer.write(partial_json)

    def _status(self, message: str, ansi_color: str, before: int) -> None:
        self.writer.line(color(message, ansi_color), before=before)
