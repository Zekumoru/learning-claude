import asyncio

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    ResultMessage,
    StreamEvent,
    EffortLevel,
)

from ..common.renderer import color, GREEN, YELLOW, CYAN, MAGENTA
from ..common.usage_tracker import init_db
from ..common.agent_usage import record_result

MODEL = "claude-haiku-4-5"

# A real reasoning task where effort makes a visible difference.
PROMPT = "How many times does the digit 7 appear across all integers from 1 to 1000?"


def build_options(effort: EffortLevel) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        model=MODEL,
        include_partial_messages=True,
        max_turns=1,
        # Enable thinking with specified effort level:
        thinking={"type": "adaptive", "display": "summarized"},
        effort=effort,
    )


async def drain_turn(client: ClaudeSDKClient) -> ResultMessage:
    """Consume one turn, streaming thinking + answer live, return the ResultMessage."""
    async for message in client.receive_response():
        match message:
            case StreamEvent(event=event):
                match event.get("type"):
                    case "content_block_start" if (
                        event.get("content_block", {}).get("type") == "thinking"
                    ):
                        print(color("[Thinking]", YELLOW))
                    # Print thinking text:
                    case "content_block_delta" if (
                        event.get("delta", {}).get("type") == "thinking_delta"
                    ):
                        print(event["delta"].get("thinking", ""), end="", flush=True)
                    case "content_block_start" if (
                        event.get("content_block", {}).get("type") == "text"
                    ):
                        print(color("\n[Answer]", GREEN))
                    case "content_block_delta" if (
                        event.get("delta", {}).get("type") == "text_delta"
                    ):
                        print(event["delta"].get("text", ""), end="", flush=True)
                    case "content_block_stop":
                        print()

            case ResultMessage() as result:
                return result

    raise RuntimeError("receive_response() ended without a ResultMessage")


async def run_at_effort(effort: EffortLevel) -> None:
    print(color(f"\n=== effort={effort} ===", CYAN))
    async with ClaudeSDKClient(options=build_options(effort)) as client:
        await client.query(PROMPT)
        result = await drain_turn(client)
        print(color(record_result(MODEL, result), MAGENTA))


async def main() -> None:
    init_db()
    # Same question, two effort levels — compare the thinking depth and tokens.
    await run_at_effort("low")
    await run_at_effort("high")


if __name__ == "__main__":
    asyncio.run(main())
