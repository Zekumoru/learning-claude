import asyncio
import shutil
import tempfile
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

from ..common.renderer import color, GREEN, CYAN, YELLOW, MAGENTA
from ..common.usage_tracker import init_db
from ..common.agent_usage import record_result

MODEL = "claude-sonnet-5"

# A throwaway dir for the agent to write into, so the run leaves no repo litter.
DEMO_DIR = tempfile.mkdtemp(prefix="perm_demo_")

# Two Write calls. Writing files is gated in "default" mode (read-only commands
# like `git status` are auto-classified safe and never prompt). On the FIRST
# Write we apply the CLI's own permission suggestions, and watch the callback go
# silent for the SECOND.
PROMPT = (
    f"Using the Write tool, create two files in {DEMO_DIR}: "
    f"'first.txt' containing the line 'hello', then 'second.txt' containing the "
    f"line 'world'. Do each as its own separate Write call, then confirm both exist."
)


async def can_use_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    context: ToolPermissionContext,
) -> PermissionResultAllow | PermissionResultDeny:
    """Apply the CLI's suggested permission updates so later calls stop asking."""

    print(color(f"\n[Callback consulted] {tool_name}", CYAN))

    if tool_name != "Write":
        return PermissionResultAllow()

    # The CLI proposes correctly-formed PermissionUpdates for this call — an
    # "accept edits for this session" mode switch plus the directory it touched.
    # Echoing them back applies them; the next Write is then auto-accepted.
    print(color(f"[Applying suggestions] {context.suggestions}", GREEN))
    return PermissionResultAllow(updated_permissions=list(context.suggestions))


def build_options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        model=MODEL,
        include_partial_messages=True,
        permission_mode="default",
        # Isolation: don't load ~/.claude or .claude/settings*.json, so no stray
        # allow-rule pre-approves the tool and bypasses the callback.
        setting_sources=[],
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
    try:
        async with ClaudeSDKClient(options=build_options()) as client:
            await client.query(PROMPT)
            result = await drain_turn(client)
            print(color(record_result(MODEL, result), MAGENTA))
    finally:
        shutil.rmtree(DEMO_DIR, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
