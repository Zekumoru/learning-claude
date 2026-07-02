import asyncio

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    ResultMessage,
    StreamEvent,
)

from ..common.renderer import color, GREEN, MAGENTA
from ..common.usage_tracker import init_db
from ..common.agent_usage import record_result

options = ClaudeAgentOptions(
    model="claude-haiku-4-5",
    system_prompt="You are a concise assistant.",
    tools=[],
    include_partial_messages=True,
    max_turns=1,
)


async def main() -> None:
    init_db()

    prompt = "In 3 short sentences, explain what a file descriptor is."

    print(color("[Response]", GREEN))
    async for message in query(prompt=prompt, options=options):
        match message:
            case StreamEvent(event=event):
                if event.get("type") == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        print(delta.get("text", ""), end="", flush=True)

            case ResultMessage() as result:
                print()
                print(color("\n[Done]", MAGENTA))
                print(record_result(options.model or "unknown", result))


if __name__ == "__main__":
    asyncio.run(main())
