from typing import Any
from anthropic.types import ToolUnionParam
from .get_current_datetime import get_current_datetime, get_current_datetime_schema
from .add_duration_to_datetime import (
    add_duration_to_datetime,
    add_duration_to_datetime_schema,
)
from .set_reminder import set_reminder, set_reminder_schema, parse_tool_datetime
from .save_article import save_article, save_article_schema
from .text_editor import handle_text_editor, text_editor_schema
from .web_search import web_search_schema
from .get_file_info import get_file_info, get_file_info_schema
from .rag_search import rag_search, rag_search_schema
from .read_media import read_media, read_media_schema

tools: list[ToolUnionParam] = [
    get_current_datetime_schema,
    add_duration_to_datetime_schema,
    set_reminder_schema,
    save_article_schema,
    text_editor_schema,
    # Note: haiku does not support web tooling, if using that model, comment:
    # web_search_schema,
    get_file_info_schema,
    rag_search_schema,
    read_media_schema,
]


def run_tool(tool_name: str, tool_input: dict[str, Any]) -> Any:
    match tool_name:
        case "get_current_datetime":
            return get_current_datetime(**tool_input)
        case "add_duration_to_datetime":
            return add_duration_to_datetime(**tool_input)
        case "set_reminder":
            if "timestamp" in tool_input:
                tool_input["timestamp"] = parse_tool_datetime(tool_input["timestamp"])
            return set_reminder(**tool_input)
        case "save_article":
            return save_article(**tool_input)
        case "str_replace_based_edit_tool":
            return handle_text_editor(tool_input)
        case "get_file_info":
            return get_file_info(**tool_input)
        case "rag_search":
            return rag_search(**tool_input)
        case "read_media":
            return read_media(**tool_input)
