from pathlib import Path
from typing import Any
from anthropic.types import ToolTextEditor20250728Param

text_editor_schema = ToolTextEditor20250728Param(
    type="text_editor_20250728",
    name="str_replace_based_edit_tool",
)


def handle_text_editor(tool_input: dict[str, Any], root: Path = Path.cwd()) -> str:
    command = tool_input["command"]
    path = root / Path(tool_input["path"])

    if not path.resolve().is_relative_to(root.resolve()):
        return f"Error: Access denied. Path must be within {root}"

    match command:
        case "view":
            return _view(path, tool_input.get("view_range"))
        case "str_replace":
            return _str_replace(path, tool_input["old_str"], tool_input["new_str"])
        case "create":
            return _create(path, tool_input["file_text"])
        case "insert":
            return _insert(path, tool_input["insert_line"], tool_input["insert_text"])
        case _:
            return f"Error: Unknown command '{command}'"


def _view(path: Path, view_range: list[int] | None = None) -> str:
    # Directory check
    if path.is_dir():
        entries = sorted(p.name + ("/" if p.is_dir() else "") for p in path.iterdir())
        return "\n".join(entries)

    # File existence check
    if not path.is_file():
        return f"Error: File not found: {path}"

    # Read the file
    lines = path.read_text(encoding="utf-8").splitlines()

    # View range handling (start, end)
    if view_range:
        start, end = view_range
        start = max(1, start)
        end = len(lines) if end == -1 else min(end, len(lines))
        lines = lines[start - 1 : end]
        start_num = start
    else:
        start_num = 1

    # Line numbering
    numbered = [f"{i}: {line}" for i, line in enumerate(lines, start=start_num)]
    return "\n".join(numbered)


def _str_replace(path: Path, old_str: str, new_str: str) -> str:
    if not path.is_file():
        return f"Error: File not found: {path}"

    content = path.read_text(encoding="utf-8")

    count = content.count(old_str)

    if count == 0:
        return "Error: No match found for replacement. Please check your text and try again."

    if count > 1:
        return f"Error: Found {count} matches for replacement text. Please provide more context to make a unique match."

    content = content.replace(old_str, new_str, 1)
    path.write_text(content, encoding="utf-8")

    return "Successfully replaced text at exactly one location."


def _create(path: Path, file_text: str) -> str:
    if path.exists():
        return f"Error: File already exists: {path}"

    # parents=True means intermediary folders are created
    # exist_ok=True means to not raise an error if directory already exists
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(file_text, encoding="utf-8")

    return f"Successfully created file {path}"


def _insert(path: Path, insert_line: int, insert_text: str) -> str:
    if not path.is_file():
        return f"Error: File not found: {path}"

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

    if insert_line < 0 or insert_line > len(lines):
        return f"Error: Line number {insert_line} is out of range (0-{len(lines)})"

    new_lines = insert_text.splitlines(keepends=True)
    if new_lines and not new_lines[-1].endswith("\n"):
        new_lines[-1] += "\n"

    lines[insert_line:insert_line] = new_lines
    path.write_text("".join(lines), encoding="utf-8")

    return f"Successfully inserted text after line {insert_line}"
