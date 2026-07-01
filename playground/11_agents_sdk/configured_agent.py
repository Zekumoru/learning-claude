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
from ..common.usage_tracker import init_db, record_usage, get_balance

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


def record_result(message: ResultMessage) -> str:
    """Record a run in the ledger; return a formatted all-time/balance line"""
    stats = message.usage or {}
    model = options.model or "unknown"
    all_time = record_usage(
        model=model,
        input_tokens=int(stats.get("input_tokens", 0)),
        output_tokens=int(stats.get("output_tokens", 0)),
        cache_creation_tokens=int(stats.get("cache_creation_input_tokens", 0)),
        cache_read_tokens=int(stats.get("cache_read_input_tokens", 0)),
        cost=message.total_cost_usd or 0.0,
    )
    balance = get_balance()
    tail = f" (balance: ${balance:.2f})" if balance is not None else ""
    return f"All-time: ${all_time:.2f}{tail}"


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
                print(record_result(result))

            # Any other non-success ending (max_turns, execution error)
            case ResultMessage(subtype=subtype, num_turns=turns) as result if (
                subtype != "success"
            ):
                print(color(f"[Ended: {subtype}]", RED))
                print(f"Turns: {turns}")
                print(record_result(result))

            # Normal completion
            case ResultMessage(num_turns=turns, total_cost_usd=cost) as result:
                print(color("[Done]", MAGENTA))
                print(f"Turns: {turns}")
                print(f"Cost: ${cost or 0.0:.4f}")
                print(record_result(result))


if __name__ == "__main__":
    asyncio.run(main())
