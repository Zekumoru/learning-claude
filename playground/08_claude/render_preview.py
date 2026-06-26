"""Preview the streaming chatbot's on-screen output WITHOUT calling the API.

`StreamConsoleRenderer` consumes a sequence of stream *events* — it doesn't care
whether they came from a real API stream. So we fabricate events with
`model_construct` (pydantic's validation-free constructor, so we set only the few
fields the renderer reads) and replay them alongside the inter-turn prints that
`run_conversation_stream` and the chatbot loop produce.

Run it:

    uv run python3 -m playground.08_claude.render_preview

This is layout-only — the wording is placeholder. It is exact for spacing,
headings, and section transitions, but cannot reproduce model-driven behavior
(pauses, file regeneration, whether the model narrates); those need a real call.
"""

from anthropic.types.beta import (
    BetaContentBlock,
    BetaRawContentBlockDelta,
    BetaRawContentBlockStartEvent,
    BetaRawContentBlockDeltaEvent,
    BetaThinkingBlock,
    BetaServerToolUseBlock,
    BetaToolUseBlock,
    BetaTextBlock,
    BetaThinkingDelta,
    BetaTextDelta,
)
from ..common.renderer import (
    StreamConsoleRenderer,
    ConsoleWriter,
    color,
    YELLOW,
    CYAN,
    GREEN,
)


def start(index: int, block: BetaContentBlock) -> BetaRawContentBlockStartEvent:
    return BetaRawContentBlockStartEvent.model_construct(
        type="content_block_start", index=index, content_block=block
    )


def delta(
    index: int, block_delta: BetaRawContentBlockDelta
) -> BetaRawContentBlockDeltaEvent:
    return BetaRawContentBlockDeltaEvent.model_construct(
        type="content_block_delta", index=index, delta=block_delta
    )


def thinking_block() -> BetaThinkingBlock:
    return BetaThinkingBlock.model_construct(type="thinking", thinking="", signature="")


def server_tool_block(name: str) -> BetaServerToolUseBlock:
    return BetaServerToolUseBlock.model_construct(
        type="server_tool_use", id="srvtoolu_x", name=name, input={}
    )


def tool_block(name: str) -> BetaToolUseBlock:
    return BetaToolUseBlock.model_construct(
        type="tool_use", id="toolu_x", name=name, input={}
    )


def text_block() -> BetaTextBlock:
    return BetaTextBlock.model_construct(type="text", text="", citations=None)


def thinking_delta(text: str) -> BetaThinkingDelta:
    return BetaThinkingDelta.model_construct(type="thinking_delta", thinking=text)


def text_delta(text: str) -> BetaTextDelta:
    return BetaTextDelta.model_construct(type="text_delta", text=text)


def print_usage(writer: ConsoleWriter, summary: str, all_time: str) -> None:
    """Mirror what run_conversation_stream + the usage tracker print per turn."""
    writer.line(color(summary, YELLOW), before=1)
    print(color(all_time, YELLOW))


def main() -> None:
    writer = ConsoleWriter()

    # Chatbot loop: the typed prompt, then the blank line before the response.
    print(color("|: ", CYAN) + "Analyze the CSV for churn drivers and save a plot.")
    print()

    # Turn 1: think, respond, then call the upload_file client tool.
    turn1 = StreamConsoleRenderer(writer=writer)
    for event in [
        start(0, thinking_block()),
        delta(0, thinking_delta("Let me upload the file first.")),
        start(1, text_block()),
        delta(1, text_delta("Let me start by reading the CSV!")),
        start(2, tool_block("upload_file")),
    ]:
        turn1.handle(event)
    print_usage(writer, "[3280 in + 110 out = 3390 tokens ($0.011)]", "[All-time: $0.86]")
    writer.gap(1)

    # Turn 2: think, run code, then narrate the result.
    turn2 = StreamConsoleRenderer(writer=writer)
    for event in [
        start(0, thinking_block()),
        delta(0, thinking_delta("Now let me analyze and plot.")),
        start(1, server_tool_block("bash_code_execution")),
        start(2, text_block()),
        delta(2, text_delta("Done! Subscription tier is the #1 churn driver.")),
    ]:
        turn2.handle(event)
    turn2.finish_inline_output()
    print_usage(
        writer, "[24178 in + 2873 out = 27051 tokens ($0.115)]", "[All-time: $1.06]"
    )

    # Chatbot downloader: leading newline separates it from the usage lines.
    print(color("\nDownloaded: churn_analysis.png", GREEN))
    print()


if __name__ == "__main__":
    main()
