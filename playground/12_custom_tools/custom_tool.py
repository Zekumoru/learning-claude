import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
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

MODEL = "claude-haiku-4-5"

# Two tool calls in one prompt — watch the loop run twice.
PROMPT = "What time is it right now in Tokyo and in New York?"


# Custom tool
class CurrentTimeArgs(TypedDict):
    timezone: Annotated[str, "IANA timezone name, e.g. 'Asia/Tokyo'"]


@tool("current_time", "Current time in an IANA timezone", CurrentTimeArgs)
async def current_time(args: CurrentTimeArgs):
    now = datetime.now(ZoneInfo(args["timezone"]))
    text = now.strftime("%Y-%m-%d %H:%M:%S %Z")
    return {"content": [{"type": "text", "text": text}]}


server = create_sdk_mcp_server(name="time_tools", tools=[current_time])


def build_options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        model=MODEL,
        include_partial_messages=True,
        mcp_servers={"time_tools": server},
        allowed_tools=["mcp__time_tools__current_time"],
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
