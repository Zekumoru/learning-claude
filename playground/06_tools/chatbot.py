from anthropic.types import MessageParam
from ..common.chat import add_user_message, run_conversation_stream, model
from .tools import tools, run_tool

messages: list[MessageParam] = []

print(f"\033[33mModel in use: {model}\033[0m\n")

while True:
    user_input = input("\033[32m|:\033[0m ")
    print()

    if user_input == "exit":
        break

    add_user_message(messages, user_input)

    run_conversation_stream(messages, tools=tools, run_tool_callback=run_tool)
