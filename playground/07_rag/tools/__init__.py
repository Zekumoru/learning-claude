from typing import Any
from collections.abc import Callable
from anthropic.types import ToolUnionParam, ToolTextEditor20250728Param
from .get_file_info import get_file_info, get_file_info_schema
from .rag_search import rag_search, rag_search_schema
from .text_editor import handle_text_editor

text_editor_schema = ToolTextEditor20250728Param(
    type="text_editor_20250728",
    name="str_replace_based_edit_tool",
)

tools: list[ToolUnionParam] = [
    text_editor_schema,
    get_file_info_schema,
    rag_search_schema,
]


def run_tool(tool_name: str, tool_input: dict[str, Any]) -> Any:
    match tool_name:
        case "get_file_info":
            return get_file_info(**tool_input)
        case "rag_search":
            return rag_search(**tool_input)
        case "str_replace_based_edit_tool":
            return handle_text_editor(tool_input)
