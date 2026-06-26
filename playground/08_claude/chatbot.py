from typing import cast
from collections.abc import Callable
from pathlib import Path
from anthropic.types import MessageParam, ToolUnionParam
from anthropic.types.beta import (
    BetaCodeExecutionTool20260120Param,
    BetaBashCodeExecutionToolResultBlock,
    BetaBashCodeExecutionResultBlock,
)
from ..common.chat import run_conversation_stream, add_user_message, client
from ..common.renderer import color, YELLOW, GREEN, CYAN
from ..common.types import AnyMessage
from ..common.tools import (
    run_tool,
    read_media_schema,
    text_editor_schema,
    upload_file_schema,
    list_files_schema,
    delete_file_schema,
)

ASSETS = Path(__file__).parent / "assets"

code_execution_tool: BetaCodeExecutionTool20260120Param = {
    "type": "code_execution_20260120",
    "name": "code_execution",
}

# The file tools and the code-execution sandbox are separate environments, and
# Claude can confuse them (Anthropic's docs warn about this when mixing client
# tools with server code execution). The sandbox can't see a local file until
# it's uploaded, so we sequence the two: upload first, run code next turn. Without
# this, the model sometimes calls upload_file and code_execution in one turn,
# orphaning the code tool use and triggering a 400 on the next request.
SYSTEM = (
    "Your file tools (upload_file, list_files, delete_file, read_media) and the "
    "code execution sandbox are separate environments. The sandbox cannot see the "
    "user's local files until they are uploaded.\n\n"
    "To analyze a local file:\n"
    "1. Call upload_file by itself and stop — wait for the upload to complete.\n"
    "2. In the FOLLOWING turn, use code_execution to analyze the now-mounted file.\n\n"
    "Never call upload_file and code_execution in the same turn."
)

messages: list[MessageParam] = []

# upload_file + code_execution are the beta pair; cast the server tool into the
# regular-typed list (chat_stream casts the whole list to beta at the boundary).
# list_files/delete_file round out workspace file management.
tools: list[ToolUnionParam] = [
    read_media_schema,
    text_editor_schema,
    upload_file_schema,
    list_files_schema,
    delete_file_schema,
    cast(ToolUnionParam, code_execution_tool),
]


def make_downloader() -> Callable[[AnyMessage], None]:
    # Fresh state per user request: `on_response` fires on every turn, and the
    # model may regenerate the same plot across turns (a new file_id but the same
    # filename), so we dedupe by filename and keep only the latest version.
    seen_ids: set[str] = set()
    seen_names: set[str] = set()

    def download(response: AnyMessage) -> None:
        for block in response.content:
            if not isinstance(block, BetaBashCodeExecutionToolResultBlock):
                continue

            result = block.content

            if not isinstance(result, BetaBashCodeExecutionResultBlock):
                continue

            for output in result.content:
                if output.file_id in seen_ids:
                    continue

                seen_ids.add(output.file_id)
                metadata = client.beta.files.retrieve_metadata(output.file_id)

                if metadata.filename in seen_names:
                    continue

                seen_names.add(metadata.filename)
                content = client.beta.files.download(output.file_id)
                output_path = ASSETS / metadata.filename
                content.write_to_file(str(output_path))
                # Leading newline separates the download line from the usage /
                # all-time lines printed just before it.
                print(color(f"\nDownloaded: {output_path.name}", GREEN))

    return download


print(
    color(
        "Chatbot with adaptive thinking, media, caching, and code execution"
        "(with Files API).\n"
        "Type 'exit' to quit.\n",
        YELLOW,
    )
)

while True:
    user_input = input(color("|: ", CYAN))

    if user_input.strip().lower() == "exit":
        break

    add_user_message(messages, user_input)
    # Blank line between the typed prompt and the assistant's first output.
    print()
    run_conversation_stream(
        messages,
        system=SYSTEM,
        thinking={"type": "adaptive"},
        tools=tools,
        run_tool_callback=run_tool,
        caching=True,
        betas=["files-api-2025-04-14"],
        on_response=make_downloader(),
    )
    print()
