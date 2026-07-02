import asyncio
from pathlib import Path

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    ToolUseBlock,
    UserMessage,
    ToolResultBlock,
    StreamEvent,
)

from ..common.renderer import color, GREEN, CYAN, MAGENTA, RED, YELLOW
from ..common.usage_tracker import init_db
from .shared import record_result

SANDBOX = Path(__file__).parent / "sandbox"

options = ClaudeAgentOptions(
    model="claude-haiku-4-5",
    system_prompt={
        "type": "preset",
        "preset": "claude_code",
        "append": "You are a careful file assistant working in a sandbox.",
    },
    tools=["Read", "Write"],
    allowed_tools=["Read"],
    permission_mode="plan",
    cwd=SANDBOX,
    include_partial_messages=True,
    max_turns=6,
)


async def drain_turn(client: ClaudeSDKClient) -> ResultMessage:
    """Consume one turn, streaming text live, return its terminal ResultMessage."""
    async for message in client.receive_response():
        match message:
            case StreamEvent(event=event):
                match event.get("type"):
                    case "content_block_start" if (
                        event.get("content_block", {}).get("type") == "text"
                    ):
                        print(color("[Response]", GREEN))
                    case "content_block_delta" if (
                        event.get("delta", {}).get("type") == "text_delta"
                    ):
                        print(event["delta"].get("text", ""), end="", flush=True)
                    case "content_block_stop":
                        print()

            case AssistantMessage(content=content):
                for block in content:
                    match block:
                        case ToolUseBlock(name=name, input=tool_input):
                            print(color("[Tool call]", CYAN))
                            print(f"{name}: {tool_input}")

            case UserMessage(content=content) if isinstance(content, list):
                for block in content:
                    match block:
                        case ToolResultBlock(content=result, is_error=is_error):
                            label = (
                                "[Tool result: ERROR]" if is_error else "[Tool result]"
                            )
                            print(color(label, RED if is_error else MAGENTA))
                            print(f"{result}\n")

            case ResultMessage() as result:
                return result

    raise RuntimeError("receive_response() ended without a ResultMessage")


async def main() -> None:
    init_db()
    SANDBOX.mkdir(exist_ok=True)

    target = SANDBOX / "notes.txt"
    target.unlink(missing_ok=True)  # start clean so the proof is honest

    async with ClaudeSDKClient(options=options) as client:
        # Turn 1 — plan mode: it proposes, but cannot write.
        print(color("=== Turn 1 (plan mode) ===", CYAN))
        await client.query("Create notes.txt containing a haiku about the sea.")
        result = await drain_turn(client)
        print(record_result(options.model or "unknown", result))
        print(color(f"File exists after planning? {target.exists()}\n", MAGENTA))

        # Promote the live session: unlock writes.
        print(color("=== Switching to acceptEdits ===\n", YELLOW))
        await client.set_permission_mode("acceptEdits")

        # Turn 2 — now it can carry out the plan.
        print(color("=== Turn 2 (acceptEdits) ===", CYAN))
        await client.query("Looks good — go ahead and create it now.")
        result = await drain_turn(client)
        print(record_result(options.model or "unknown", result))
        print(color(f"File exists after executing? {target.exists()}", MAGENTA))


if __name__ == "__main__":
    asyncio.run(main())
