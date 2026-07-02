import asyncio
from typing import Any

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    ResultMessage,
    StreamEvent,
)

from ..common.renderer import color, format_usage, GREEN, MAGENTA, RED
from ..common.usage_tracker import init_db
from .shared import record_result

options = ClaudeAgentOptions(
    model="claude-haiku-4-5",
    system_prompt="You are a verbose writer who loves long, detailed answer.",
    tools=[],
    include_partial_messages=True,
    max_turns=1,
)


def merge_stream_usage(usage: dict[str, int], event: dict[str, Any]) -> None:
    """Scrape token counts from raw stream events. These survive an interrupt,
    unlike ResultMessage.usage, which comes back empty on an aborted run."""
    match event.get("type"):
        case "message_start":
            u = event.get("message", {}).get("usage", {})
            usage["input_tokens"] = u.get("input_tokens", 0)
            usage["cache_creation_input_tokens"] = u.get(
                "cache_creation_input_tokens", 0
            )
            usage["cache_read_input_tokens"] = u.get("cache_read_input_tokens", 0)
            usage["output_tokens"] = u.get("output_tokens", 0)
        case "message_delta":
            u = event.get("usage", {})
            usage["output_tokens"] = u.get(
                "output_tokens", usage.get("output_tokens", 0)
            )


async def consume(
    client: ClaudeSDKClient,
    streaming_started: asyncio.Event,
    usage: dict[str, int],
) -> ResultMessage | None:
    """Drain the stream, print text deltas live, return the terminal ResultMessage."""

    result: ResultMessage | None = None

    async for message in client.receive_response():
        match message:
            case StreamEvent(event=event):
                merge_stream_usage(usage, event)
                if event.get("type") == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        print(delta.get("text", ""), end="", flush=True)
                        streaming_started.set()  # signal main that text is flowing

            case ResultMessage() as msg:
                result = msg

    return result


async def main() -> None:
    init_db()

    prompt = (
        "Write a very long, detailed essay about the history of the printing press."
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)

        print(
            color("[Response ", GREEN),
            color("(streaming will interrupt in 2s)", RED),
            color("]", GREEN),
            sep="",
        )

        streaming_started = asyncio.Event()
        usage: dict[str, int] = {}
        consume_task = asyncio.create_task(consume(client, streaming_started, usage))

        await streaming_started.wait()  # don't interrupt until text is actually flowing

        await asyncio.sleep(3)  # stream a bit more then cut

        print(color("\n\n[Sending interrupt...]", RED))
        await client.interrupt()

        result = await consume_task

        print(color("\n[Done]", MAGENTA))
        if result is not None:
            print(f"Ended: {result.subtype}")
            print(record_result(options.model or "unknown", result))

            # Prefer the SDK's own tally; fall back to stream-scraped counts on an interrupt.
            tally = (
                result.usage
                if result.usage and result.usage.get("input_tokens")
                else usage
            )

            print()
            print(
                format_usage(
                    options.model or "unknown",
                    tally,
                    cost=result.total_cost_usd,
                )
            )


if __name__ == "__main__":
    asyncio.run(main())
