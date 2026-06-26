from typing import TypedDict
from anthropic.types import ToolParam
from ..chat import client


class DeleteFileResult(TypedDict):
    id: str
    deleted: bool


delete_file_schema: ToolParam = {
    "name": "delete_file",
    "description": (
        "Permanently delete a file from the workspace by its file id. Use this to "
        "clean up files that are no longer needed. This cannot be undone."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "file_id": {
                "type": "string",
                "description": "The id of the file to delete (e.g. from list_files).",
            }
        },
        "required": ["file_id"],
    },
}


def delete_file(file_id: str) -> DeleteFileResult:
    result = client.beta.files.delete(file_id)
    return {"id": result.id, "deleted": True}
