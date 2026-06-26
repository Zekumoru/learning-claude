import mimetypes
from pathlib import Path
from anthropic.types import ToolParam
from anthropic.types.beta import BetaContainerUploadBlockParam
from ..chat import client

upload_file_schema: ToolParam = {
    "name": "upload_file",
    "description": (
        "Upload a local data file (CSV, Excel, JSON, image, etc.) so it can be "
        "analyzed with the code execution tool. Use this when the user asks you "
        "to analyze, process, or visualize a file on their machine. Once "
        "uploaded, the file is mounted in the code execution container."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "The file's path, relative to the working directory.",
            }
        },
        "required": ["filename"],
    },
}

UploadResult = list[BetaContainerUploadBlockParam] | dict[str, str]


def _error(message: str) -> dict[str, str]:
    return {"error": message}


def upload_file(filename: str, root: Path | None = None) -> UploadResult:
    root = (Path.cwd() if root is None else root).resolve()
    file_path = (root / Path(filename)).resolve()

    if not file_path.is_relative_to(root):
        return _error(f"Access denied. Path must be within {root}.")

    if not file_path.is_file():
        return _error(f"File not found: {filename}")

    mime_type, _ = mimetypes.guess_type(file_path.name)

    with open(file_path, "rb") as f:
        file_object = client.beta.files.upload(
            file=(file_path.name, f, mime_type or "application/octet-stream")
        )

    return [{"type": "container_upload", "file_id": file_object.id}]
