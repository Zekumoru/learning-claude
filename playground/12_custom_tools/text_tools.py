import asyncio
import json
import re
from typing import Annotated, TypedDict

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
from claude_agent_sdk import tool, create_sdk_mcp_server

from ..common.renderer import color, GREEN, CYAN, YELLOW, MAGENTA
from ..common.usage_tracker import init_db
from ..common.agent_usage import record_result

MODEL = "claude-sonnet-5"

# One paragraph, two questions → Claude calls both tools in one turn.
PROMPT = (
    "Analyze this release note: 'The scheduler now batches outbound "
    "notifications and deduplicates recipients before dispatch. This "
    "significantly reduces redundant network calls under high load.' "
    "Give me its text stats and its three longest words."
)


class TextStatArgs(TypedDict):
    text: Annotated[str, "The text to analyze"]


class LongestWordsArgs(TypedDict):
    text: Annotated[str, "The text to search"]
    count: Annotated[int, "How many of the longest words to return"]


class TextStats(TypedDict):
    characters: int
    words: int
    sentences: int
    reading_seconds: int


class LongestWords(TypedDict):
    words: list[str]


@tool(
    "text_stats", "Character, word, and sentence counts plus reading time", TextStatArgs
)
async def text_stats(args: TextStatArgs):
    text = args["text"]
    words = text.split()
    stats: TextStats = {
        "characters": len(text),
        "words": len(words),
        "sentences": len(re.findall(r"[.!?]+", text)),
        "reading_seconds": round(len(words) / 200 * 60),  # 200 words/min
    }
    return {"content": [{"type": "text", "text": json.dumps(stats)}]}


@tool("longest_words", "The N longest unique words in the text", LongestWordsArgs)
async def longest_words(args: LongestWordsArgs):
    found = re.findall(r"[A-Za-z']+", args["text"])
    unique = list(dict.fromkeys(found))  # dedupe, keep first-seen order
    ranked = sorted(unique, key=lambda w: (-len(w), w.lower()))
    result: LongestWords = {"words": ranked[: args["count"]]}
    return {"content": [{"type": "text", "text": json.dumps(result)}]}


server = create_sdk_mcp_server(name="text_tools", tools=[text_stats, longest_words])


def build_options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        model=MODEL,
        include_partial_messages=True,
        mcp_servers={"text_tools": server},
        allowed_tools=[
            "mcp__text_tools__text_stats",
            "mcp__text_tools__longest_words",
        ],
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


# --- Note: server-side tools (read-only) ---------------------------------
# The tools above run in-process. Anthropic also ships *server-side* tools
# that run on their infrastructure — you opt in by name instead of writing a
# handler. E.g. to let Claude search the web, add the built-in name to
# allowed_tools (no @tool, no create_sdk_mcp_server):
#
#     ClaudeAgentOptions(allowed_tools=["WebSearch"])
#
# Not wired up here — a live web search bills against the run. This just
# marks where a server-side tool would plug in.

if __name__ == "__main__":
    asyncio.run(main())
