import asyncio

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ResultMessage,
)


async def main():
    options = ClaudeAgentOptions(
        allowed_tools=["Glob", "Read"],
        permission_mode="dontAsk",
    )

    async for message in query(
        prompt="Look at the current directory and tell me what files are here.",
        options=options,
    ):
        match message:
            case AssistantMessage(content=content):
                for block in content:
                    match block:
                        case TextBlock(text=text):
                            print(text)

            case ResultMessage(num_turns=num_turns, total_cost_usd=total_cost_usd):
                print("\nDone.")
                print("Turns:", num_turns)
                print("Cost:", total_cost_usd)

            case _:
                pass


if __name__ == "__main__":
    asyncio.run(main())
