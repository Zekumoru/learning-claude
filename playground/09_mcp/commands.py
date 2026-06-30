import re
from collections.abc import Iterable

from anthropic.types import MessageParam
from mcp.types import Prompt, PromptMessage, TextContent
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document

from ..common.renderer import RED, color
from .client import MCPClient


class CommandCompleter(Completer):
    def __init__(self, command_names: list[str], doc_ids: list[str]) -> None:
        self._command_names = command_names
        self._doc_ids = doc_ids

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        text = document.text_before_cursor

        # Still typing the command name
        name_match = re.match(r"/([\w\-]*)$", text)
        if name_match is not None:
            prefix = name_match.group(1)
            for name in self._command_names:
                if name.startswith(prefix):
                    yield Completion(name, start_position=-len(prefix))
            return

        # Typing an argument after a known command
        arg_match = re.match(r"^/([\w\-]+)\s+(\S*)$", text)
        if arg_match is not None:
            command, prefix = arg_match.group(1), arg_match.group(2)
            if command in self._command_names:
                for doc_id in self._doc_ids:
                    if doc_id.startswith(prefix):
                        yield Completion(doc_id, start_position=-len(prefix))


def parse_command(text: str) -> tuple[str, list[str]] | None:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None

    parts = stripped[1:].split()
    if not parts:
        return None

    return parts[0], parts[1:]


def _to_message_param(message: PromptMessage) -> MessageParam:
    content = message.content
    if isinstance(content, TextContent):
        return {"role": message.role, "content": content.text}
    raise ValueError(f"Unsupported prompt message content: {type(content).__name__}")


async def expand_command(
    client: MCPClient,
    session: PromptSession[str],
    command: str,
    arg_values: list[str],
    prompts: list[Prompt],
) -> list[MessageParam] | None:
    prompt = next((p for p in prompts if p.name == command), None)

    if prompt is None:
        print(color(f"Unknown command: /{command}", RED))
        return None

    args: dict[str, str] = {}
    for index, argument in enumerate(prompt.arguments or []):
        if index < len(arg_values):
            args[argument.name] = arg_values[index]
        else:
            args[argument.name] = await session.prompt_async(f"  {argument.name}: ")

    prompt_messages = await client.get_prompt(command, args)
    return [_to_message_param(message) for message in prompt_messages]
