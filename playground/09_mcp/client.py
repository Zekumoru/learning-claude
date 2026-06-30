import asyncio
import json
from pydantic import AnyUrl
from contextlib import AsyncExitStack
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, Prompt, PromptMessage, TextResourceContents, Tool

REPO_ROOT = Path(__file__).resolve().parents[2]


class MCPClient:
    def __init__(self, command: str, args: list[str]) -> None:
        self._command = command
        self._args = args
        self._session: ClientSession | None = None
        self._exit_stack = AsyncExitStack()

    async def connect(self) -> None:
        params = StdioServerParameters(
            command=self._command, args=self._args, cwd=str(REPO_ROOT)
        )

        read, write = await self._exit_stack.enter_async_context(stdio_client(params))
        session = await self._exit_stack.enter_async_context(ClientSession(read, write))

        await session.initialize()

        self._session = session

    async def cleanup(self) -> None:
        await self._exit_stack.aclose()
        self._session = None

    def session(self) -> ClientSession:
        if self._session is None:
            raise ConnectionError(
                "Client is not connected. Use 'async with MCPClient(...)' or call connect() first."
            )
        return self._session

    async def list_tools(self) -> list[Tool]:
        result = await self.session().list_tools()
        return result.tools

    async def call_tool(
        self, tool_name: str, tool_input: dict[str, Any]
    ) -> CallToolResult:
        return await self.session().call_tool(tool_name, tool_input)

    async def read_resource(self, uri: str) -> Any:
        result = await self.session().read_resource(AnyUrl(uri))
        resource = result.contents[0]

        match resource:
            case TextResourceContents():
                if resource.mimeType == "application/json":
                    return json.loads(resource.text)
                return resource.text
            case _:
                raise ValueError(
                    f"Unsupported resource content for {uri}: {type(resource).__name__}"
                )

    async def list_prompts(self) -> list[Prompt]:
        result = await self.session().list_prompts()
        return result.prompts

    async def get_prompt(
        self, prompt_name: str, args: dict[str, str]
    ) -> list[PromptMessage]:
        result = await self.session().get_prompt(prompt_name, args)
        return result.messages

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.cleanup()


async def main() -> None:
    async with MCPClient(
        command="uv", args=["run", "playground/09_mcp/server.py"]
    ) as client:
        tools = await client.list_tools()
        for tool in tools:
            print(f"{tool.name}: {tool.description}")


if __name__ == "__main__":
    asyncio.run(main())
