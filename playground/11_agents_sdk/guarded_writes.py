import asyncio
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ToolPermissionContext,
    PermissionResult,
    PermissionResultAllow,
    PermissionResultDeny,
    UserMessage,
    ToolResultBlock,
)

from ..common.renderer import color, GREEN, CYAN, MAGENTA, RED
from ..common.usage_tracker import init_db
from ..common.agent_usage import record_result

SANDBOX = Path(__file__).parent / "sandbox"


READONLY_BASH = {"ls", "cat", "pwd", "echo", "head", "tail", "grep", "find", "wc"}


async def can_use_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    context: ToolPermissionContext,
) -> PermissionResult:
    """Answer permission prompts in code: gate Write to sandbox/, Bash to read-only."""
    match tool_name:
        case "Write":
            target = Path(tool_input.get("file_path", "")).resolve()
            if target.is_relative_to(SANDBOX.resolve()):
                print(color(f"[Allowed] Write: {target}", GREEN))
                return PermissionResultAllow()
            print(color(f"[Denied] Write: {target} (outside sandbox)", RED))
            return PermissionResultDeny(
                message=f"Writes are only allowed inside {SANDBOX.name}/"
            )

        case "Bash":
            command = tool_input.get("command", "")
            first = command.split()[0] if command.split() else ""
            if first in READONLY_BASH:
                print(color(f"[Allowed] Bash: {command}", GREEN))
                return PermissionResultAllow()
            print(color(f"[Denied] Bash: {command} (not read-only)", RED))
            return PermissionResultDeny(
                message=f"Only read-only commands are allowed: {sorted(READONLY_BASH)}"
            )

        case _:
            return PermissionResultAllow()


options = ClaudeAgentOptions(
    model="claude-haiku-4-5",
    system_prompt={
        "type": "preset",
        "preset": "claude_code",
        "append": "You are a careful file assistant working in a sandbox.",
    },
    tools=["Read", "Write", "Bash"],
    allowed_tools=["Read"],
    # disallowed_tools=["Bash"],
    can_use_tool=can_use_tool,
    permission_mode="default",
    cwd=Path(__file__).parent,
    max_turns=6,
)


async def main() -> None:
    init_db()

    SANDBOX.mkdir(exist_ok=True)

    prompt = (
        "Use the Bash tool for two steps: "
        "first run `ls` to list the files in this directory, "
        "then run `rm -f notes.txt` to clean up. Do both steps."
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for message in client.receive_response():
            match message:
                case AssistantMessage(content=content):
                    for block in content:
                        match block:
                            case TextBlock(text=text):
                                print(color("[CLAUDE]", GREEN))
                                print(f"{text}\n")
                            case ToolUseBlock(name=name, input=tool_input):
                                print(color("[Tool call]", CYAN))
                                print(f"{name}: {tool_input}\n")

                # Tool results re-enter the loop as a UserMessage (list content)
                case UserMessage(content=content) if isinstance(content, list):
                    for block in content:
                        match block:
                            case ToolResultBlock(content=result, is_error=is_error):
                                label = (
                                    "[Tool result: ERROR]"
                                    if is_error
                                    else "[Tool result]"
                                )
                                print(color(label, RED if is_error else MAGENTA))
                                print(f"{result}\n")

                case ResultMessage(num_turns=turns, total_cost_usd=cost) as result:
                    print(color("[Done]", MAGENTA))
                    print(f"Turns: {turns}")
                    print(f"Cost: ${cost or 0.0:.4f}")
                    print(record_result(options.model or "unknown", result))


if __name__ == "__main__":
    asyncio.run(main())
