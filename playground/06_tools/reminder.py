from anthropic.types import MessageParam
from ..common.chat import run_conversation, add_user_message
from .tools import tools, run_tool

messages: list[MessageParam] = []

add_user_message(
    messages,
    "Set a reminder for testing the reminder tool. It should remind me in a minute that it worked.",
)

run_conversation(messages, tools=tools, run_tool_callback=run_tool)
