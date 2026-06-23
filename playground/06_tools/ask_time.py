from anthropic.types import MessageParam
from ..common.chat import run_conversation, add_user_message
from ..common.tools import get_current_datetime_schema, run_tool

messages: list[MessageParam] = []

add_user_message(
    messages,
    "What is the current time in HH:MM format? Also, what is the current time in SS format?",
)

run_conversation(
    messages, tools=[get_current_datetime_schema], run_tool_callback=run_tool
)
