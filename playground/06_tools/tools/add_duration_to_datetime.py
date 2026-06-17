from datetime import datetime as DateTime, timedelta
from anthropic.types import ToolParam


def add_duration_to_datetime(
    datetime: str,
    duration: int | float = 0,
    unit: str = "days",
    input_format: str = "%Y-%m-%d",
) -> str:
    if not datetime:
        raise ValueError("datetime cannot be empty")

    if not input_format:
        raise ValueError("input_format cannot be empty")

    allowed_units = {
        "seconds": "seconds",
        "minutes": "minutes",
        "hours": "hours",
        "days": "days",
        "weeks": "weeks",
    }

    if unit not in allowed_units:
        raise ValueError(
            f"Unsupported unit '{unit}'. Supported units are: "
            f"{', '.join(allowed_units.keys())}"
        )

    parsed_datetime = DateTime.strptime(datetime, input_format)

    delta = timedelta(**{allowed_units[unit]: duration})
    result = parsed_datetime + delta

    return result.strftime(input_format)


add_duration_to_datetime_schema = ToolParam(
    {
        "name": "add_duration_to_datetime",
        "description": (
            "Adds a duration to a datetime string and returns the resulting datetime formatted as a string. "
            "Use this tool when the model needs to calculate a future or past datetime by adding seconds, minutes, hours, days, or weeks to a known datetime. "
            "Do not use this tool for calendar-sensitive operations such as adding months or years, or for timezone conversion. "
            "The result is returned using the same format specified by input_format."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "datetime": {
                    "type": "string",
                    "description": (
                        "The input datetime string to modify. "
                        "It must exactly match the format specified by input_format."
                    ),
                    "examples": ["2026-06-17", "2026-06-17 14:30:00"],
                },
                "duration": {
                    "type": "number",
                    "description": (
                        "The amount of time to add to the datetime. "
                        "Use a negative number to subtract time instead."
                    ),
                    "default": 0,
                    "examples": [3, -2, 1.5],
                },
                "unit": {
                    "type": "string",
                    "description": "The unit of time represented by duration.",
                    "enum": ["seconds", "minutes", "hours", "days", "weeks"],
                    "default": "days",
                },
                "input_format": {
                    "type": "string",
                    "description": (
                        "The Python strptime/strftime format used to parse the input datetime "
                        "and format the returned result."
                    ),
                    "default": "%Y-%m-%d",
                    "examples": ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S"],
                },
            },
            "required": ["datetime"],
            "additionalProperties": False,
        },
    }
)
