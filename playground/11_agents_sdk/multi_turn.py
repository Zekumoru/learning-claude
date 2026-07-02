import asyncio
from pathlib import Path

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    UserMessage,
    ToolResultBlock,
)

from ..common.renderer import color, GREEN, CYAN, MAGENTA, RED
from ..common.usage_tracker import init_db
from ..common.agent_usage import record_result

options = ClaudeAgentOptions(
    model="claude-haiku-4-5",
    system_prompt={
        "type": "preset",
        "preset": "claude_code",
        "append": "You are a concise assistant exploring a small repo.",
    },
    tools=["Read", "Glob"],
    allowed_tools=["Read", "Glob"],
    permission_mode="dontAsk",
    cwd=Path(__file__).parent,
    max_turns=6,
)


async def drain_turn(client: ClaudeSDKClient) -> ResultMessage:
    """Consume one turn's messages, print them, and returns its terminal ResultMessage."""

    async for message in client.receive_response():
        match message:
            case AssistantMessage(content=content):
                for block in content:
                    match block:
                        case TextBlock(text=text):
                            print(color("[Response]", GREEN))
                            print(f"{text}\n")
                        case ToolUseBlock(name=name, input=tool_input):
                            print(color("[Tool call]", CYAN))
                            print(f"{name}: {tool_input}\n")

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

    async with ClaudeSDKClient(options=options) as client:
        # Turn 1
        print(color("=== Turn 1 ===", CYAN))
        await client.query("List the Python files in this directory.")
        result = await drain_turn(client)
        print(record_result(options.model or "unknown", result))

        # Turn 2 (refers to turn 1 without restating it)
        print(color("\n=== Turn 2 ===", CYAN))
        await client.query("Of those, which one is the shortest? Just name it.")
        result = await drain_turn(client)
        print(record_result(options.model or "unknown", result))


if __name__ == "__main__":
    asyncio.run(main())
