from anthropic.types import MessageParam
from ..common.chat import (
    add_user_message,
    run_conversation_stream,
)
from .tools import tools, run_tool

messages: list[MessageParam] = []

while True:
    user_input = input("|: ")

    if user_input == "exit":
        break

    add_user_message(messages, user_input)

    run_conversation_stream(messages, tools=tools, run_tool_callback=run_tool)
