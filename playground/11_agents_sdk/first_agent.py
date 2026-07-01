import asyncio
from pathlib import Path

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    UserMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
)
from ..common.renderer import format_usage, color, GREEN, CYAN, YELLOW, MAGENTA
from ..common.usage_tracker import init_db, record_usage

options = ClaudeAgentOptions(
    model="claude-haiku-4-5",
    system_prompt="You are a concise assistant exploring a code directory",
    allowed_tools=["Glob", "Read", "Grep"],
    permission_mode="dontAsk",
    cwd=Path(__file__).parent,
    max_turns=5,
)


async def main() -> None:
    init_db()

    prompt = (
        "List the Python files in the current directory and give me a "
        "one-sentence summary of what each one does."
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

            case UserMessage(content=content):
                # The SDK feeds tool results back to Claude as a UserMessage.
                if isinstance(content, list):
                    for block in content:
                        match block:
                            case ToolResultBlock(content=result):
                                preview = str(result)[:120]
                                print(color("[Tool result]", YELLOW))
                                print(f"{preview}...\n")

            case ResultMessage(num_turns=num_turns, total_cost_usd=cost, usage=usage):
                stats = usage or {}
                model = options.model or "unknown"
                all_time_cost = record_usage(
                    model=model,
                    input_tokens=int(stats.get("input_tokens", 0)),
                    output_tokens=int(stats.get("output_tokens", 0)),
                    cache_creation_tokens=int(
                        stats.get("cache_creation_input_tokens", 0)
                    ),
                    cache_read_tokens=int(stats.get("cache_read_input_tokens", 0)),
                    cost=cost or 0.0,
                )
                print(color("[Done]", MAGENTA))
                print(f"  turns:    {num_turns}")
                print(f"  cost:     ${cost:.4f}")
                print(f"  usage:    {format_usage(model, stats, cost=-1)}")
                print(f"  all-time: ${all_time_cost:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
