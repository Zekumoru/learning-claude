import asyncio
from typing import Any, cast

from anthropic import AsyncAnthropic
from anthropic.types import (
    MessageParam,
    ModelParam,
    ToolParam,
    ToolResultBlockParam,
    ToolUseBlock,
)
from mcp.types import TextContent, Tool
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import merge_completers

from ..common.chat import add_assistant_message, add_user_message, max_tokens
from ..common.renderer import CYAN, GREEN, MAGENTA, YELLOW, color, format_usage
from ..common.usage_tracker import init_db, on_usage
from .client import MCPClient
from .commands import CommandCompleter, expand_command, parse_command
from .mentions import DocumentCompleter, inject_mentions, prompt_user

model: ModelParam = "claude-haiku-4-5"


def to_anthropic_tool(tool: Tool) -> ToolParam:
    return cast(
        ToolParam,
        {
            "name": tool.name,
            "description": tool.description or "",
            "input_schema": tool.inputSchema,
        },
    )


async def run_turn(
    mcp: MCPClient,
    client: AsyncAnthropic,
    messages: list[MessageParam],
    tools: list[ToolParam],
) -> None:
    while True:
        async with client.messages.stream(
            model=model, max_tokens=max_tokens, messages=messages, tools=tools
        ) as stream:
            printed_header = False
            if stream.text_stream:
                print(color("\n[Response]", GREEN))
                printed_header = True

            async for text in stream.text_stream:
                print(text, end="", flush=True)

            if printed_header:
                print()
            final = await stream.get_final_message()

        add_assistant_message(messages, final)
        print()
        print(format_usage(final.model, final.usage))
        on_usage(final)

        tool_uses = [
            block for block in final.content if isinstance(block, ToolUseBlock)
        ]
        if not tool_uses:
            return

        results: list[ToolResultBlockParam] = []
        for tool_use in tool_uses:
            print(color(f"\n[running {tool_use.name}...]\n", MAGENTA))
            result = await mcp.call_tool(
                tool_use.name, cast(dict[str, Any], tool_use.input)
            )
            output = "\n".join(
                c.text for c in result.content if isinstance(c, TextContent)
            )
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": output,
                    "is_error": bool(result.isError),
                }
            )

        add_user_message(messages, results)


async def main() -> None:
    init_db()

    client = AsyncAnthropic()
    session: PromptSession[str] = PromptSession()
    messages: list[MessageParam] = []

    async with MCPClient(
        command="uv", args=["run", "playground/09_mcp/server.py"]
    ) as mcp:
        tools = [to_anthropic_tool(tool) for tool in await mcp.list_tools()]
        doc_ids: list[str] = await mcp.read_resource("docs://documents")
        prompts = await mcp.list_prompts()
        completer = merge_completers(
            [
                DocumentCompleter(doc_ids),
                CommandCompleter([p.name for p in prompts], doc_ids),
            ]
        )

        print(
            color(
                "MCP Document Chat\nType @ to mention a document, 'exit' to quit.\n",
                CYAN,
            )
        )

        while True:
            user_input = await prompt_user(session, completer)

            if user_input.strip().lower() == "exit":
                break

            parsed = parse_command(user_input)
            if parsed is not None:
                command, arg_values = parsed
                prompt_messages = await expand_command(
                    mcp, session, command, arg_values, prompts
                )
                if prompt_messages is None:
                    continue
                messages.extend(prompt_messages)
            else:
                prompt = await inject_mentions(mcp, user_input)
                add_user_message(messages, prompt)

            await run_turn(mcp, client, messages, tools)
            print()


if __name__ == "__main__":
    asyncio.run(main())
