import asyncio
from pathlib import Path

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from ..common.renderer import color, GREEN, CYAN, MAGENTA, RED
from ..common.usage_tracker import init_db
from ..common.agent_usage import record_result

options = ClaudeAgentOptions(
    model="claude-haiku-4-5",
    # Preset identity + own instructions:
    system_prompt={
        "type": "preset",
        "preset": "claude_code",
        "append": "You are auditing a small learning repo. Be terse.",
    },
    # `tools` genuinely limits the toolbox, not just auto-approval:
    tools=["Glob", "Read", "Grep"],
    allowed_tools=["Glob", "Read", "Grep"],
    permission_mode="dontAsk",
    setting_sources=["project"],  # loads CLAUDE.md so the agent knows the repo
    cwd=Path(__file__).parent,
    max_turns=5,
    max_budget_usd=0.10,  # hard stop by putting cheap ceiling,
)


async def main() -> None:
    init_db()

    prompt = (
        "Audit this directory: list the Python files and, in one line each, "
        "say what each does. Read whatever you need."
    )

    async for message in query(prompt=prompt, options=options):
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

            # Budget ceiling hit
            case ResultMessage(
                subtype="error_max_budget_usd", total_cost_usd=cost
            ) as result:
                ceiling = options.max_budget_usd or 0.0
                print(color("[Budget stop]", RED))
                print(f"Hit the ${ceiling:.2f} ceiling (spent ${cost or 0.0:.4f})")
                print(record_result(options.model or "unknown", result))

            # Any other non-success ending (max_turns, execution error)
            case ResultMessage(subtype=subtype, num_turns=turns) as result if (
                subtype != "success"
            ):
                print(color(f"[Ended: {subtype}]", RED))
                print(f"Turns: {turns}")
                print(record_result(options.model or "unknown", result))

            # Normal completion
            case ResultMessage(num_turns=turns, total_cost_usd=cost) as result:
                print(color("[Done]", MAGENTA))
                print(f"Turns: {turns}")
                print(f"Cost: ${cost or 0.0:.4f}")
                print(record_result(options.model or "unknown", result))


if __name__ == "__main__":
    asyncio.run(main())
