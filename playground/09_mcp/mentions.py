import re
from collections.abc import Iterable

from mcp import McpError
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document

from .client import MCPClient

# @doc_id -> letters, digits, dot, dash, underscore (covers "report.pdf" etc.)
MENTION_PATTERN = re.compile(r"@([\w.\-]+)")


class DocumentCompleter(Completer):
    def __init__(self, doc_ids: list[str]) -> None:
        self._doc_ids = doc_ids

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        match = re.search(r"@([\w.\-]*)$", document.text_before_cursor)

        if match is None:
            return

        prefix = match.group(1)
        for doc_id in self._doc_ids:
            if doc_id.startswith(prefix):
                yield Completion(doc_id, start_position=-len(prefix))


async def prompt_user(
    session: PromptSession[str], doc_ids: list[str], message: str = "|: "
) -> str:
    return await session.prompt_async(message, completer=DocumentCompleter(doc_ids))


async def inject_mentions(client: MCPClient, user_input: str) -> str:
    doc_ids = list(dict.fromkeys(MENTION_PATTERN.findall(user_input)))
    if not doc_ids:
        return user_input

    blocks: list[str] = []
    for doc_id in doc_ids:
        try:
            content = await client.read_resource(f"docs://documents/{doc_id}")
        except McpError:
            # The server raises on an unknown id; it reaches us as McpError
            # (not the server's ValueError). Do not crash if not a
            # valid document mention.
            continue
        blocks.append(f'<document id="{doc_id}">\n{content}\n</document>')

    if not blocks:
        return user_input
    return "\n".join(blocks) + "\n\n" + user_input
