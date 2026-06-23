from pathlib import Path
from anthropic.types import ToolParam

get_file_info_schema: ToolParam = {
    "name": "get_file_info",
    "description": (
        "Get metadata about a file: line count, character count, and size in bytes. "
        "Use this to decide whether to read the file directly with the text editor "
        "or search it with rag_search."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The path to the file."},
        },
        "required": ["path"],
    },
}


def get_file_info(path: str, root: Path = Path.cwd()) -> dict[str, str | int]:
    file_path = (root / Path(path)).resolve()

    if not file_path.is_relative_to(root.resolve()):
        return {"error": f"Access denied. Path must be within {root}"}

    if not file_path.is_file():
        return {"error": f"File not found: {path}"}

    content = file_path.read_text(encoding="utf-8")

    return {
        "path": path,
        "lines": content.count("\n") + 1,
        "characters": len(content),
        "size_bytes": file_path.stat().st_size,
    }
