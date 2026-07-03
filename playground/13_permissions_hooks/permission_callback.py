import asyncio
from typing import Any

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    UserMessage,
    ResultMessage,
    ToolUseBlock,
    ToolResultBlock,
    StreamEvent,
)
from claude_agent_sdk import (
    ToolPermissionContext,
    PermissionResultAllow,
    PermissionResultDeny,
)

from ..common.renderer import color, GREEN, CYAN, YELLOW, MAGENTA, RED
from ..common.usage_tracker import init_db
from ..common.agent_usage import record_result

MODEL = "claude-sonnet-5"

# One safe command, one destructive one → watch the callback allow the first
# and deny the second with a reason the model then has to work around.
PROMPT = (
    "Do two things with the Bash tool, each in its own call: "
    "first, print the current working directory. "
    "then, delete every .log file in this directory with rm."
)

# Substrings that make a shell command destructive enough to block outright.
BLOCKED = ("rm ", "sudo", "mkfs", "dd ", ":(){", "shutdown", "reboot")


async def can_use_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    context: ToolPermissionContext,
) -> PermissionResultAllow | PermissionResultDeny:
    """Runtime gate: inspect each tool call's actual arguments and allow or deny."""

    if tool_name != "Bash":
        return PermissionResultAllow()

    command = tool_input.get("command", "")
    if any(bad in command for bad in BLOCKED):
        print(color(f"\n[Denied] {command}", RED))
        return PermissionResultDeny(
            message=f"Blocked: '{command}' matches a destructive pattern. "
            "Do not use rm/sudo/etc. — suggest the command instead of running it.",
        )

    return PermissionResultAllow()


def build_options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        model=MODEL,
        include_partial_messages=True,
        allowed_tools=["Bash"],
        can_use_tool=can_use_tool,
    )


async def drain_turn(client: ClaudeSDKClient) -> ResultMessage:
    """Consume one turn: stream the answer live, surface each tool call/result."""
    answering = False
    async for message in client.receive_response():
        match message:
            case StreamEvent(event=event):
                match event.get("type"):
                    case "content_block_delta" if (
                        event.get("delta", {}).get("type") == "text_delta"
                    ):
                        if not answering:
                            print(color("\n[Answer]", GREEN))
                            answering = True
                        print(event["delta"].get("text", ""), end="", flush=True)

            case AssistantMessage(content=content):
                for block in content:
                    match block:
                        case ToolUseBlock(name=name, input=tool_input):
                            print(color("\n[Tool call]", CYAN))
                            print(f"{name}: {tool_input}")

            case UserMessage(content=content):
                if isinstance(content, list):
                    for block in content:
                        match block:
                            case ToolResultBlock(content=result):
                                print(color("[Tool result]", YELLOW))
                                print(f"{str(result)[:200]}")

            case ResultMessage() as result:
                print()
                return result

    raise RuntimeError("receive_response() ended without a ResultMessage")


async def main() -> None:
    init_db()
    async with ClaudeSDKClient(options=build_options()) as client:
        await client.query(PROMPT)
        result = await drain_turn(client)
        print(color(record_result(MODEL, result), MAGENTA))


if __name__ == "__main__":
    asyncio.run(main())
