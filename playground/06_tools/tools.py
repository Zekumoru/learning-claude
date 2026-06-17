from datetime import datetime
from anthropic.types import ToolParam, ToolUnionParam
from typing import cast, Any


def get_current_datetime(date_format="%Y-%m-%d %H:%M:%S"):
    if not date_format:
        raise ValueError("date_format cannot be empty")
    return datetime.now().strftime(date_format)


get_current_datetime_schema = ToolParam(
    {
        "name": "get_current_datetime",
        "description": "Returns the current local date and time formatted as a string using a Python strftime-compatible format.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_format": {
                    "type": "string",
                    "description": (
                        "Optional Python strftime format string used to format the current datetime. "
                        "Must not be empty. Defaults to '%Y-%m-%d %H:%M:%S'."
                    ),
                    "default": "%Y-%m-%d %H:%M:%S",
                    "minLength": 1,
                }
            },
            "required": [],
            "additionalProperties": False,
        },
    }
)


tools: list[ToolUnionParam] = [get_current_datetime_schema]


def run_tool(tool_name: str, tool_input: dict[str, Any]) -> Any:
    if tool_name == "get_current_datetime":
        return get_current_datetime(**tool_input)


if __name__ == "__main__":
    print(get_current_datetime(""))
