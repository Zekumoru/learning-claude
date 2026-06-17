from anthropic.types import MessageParam
from ..common.chat import (
    chat,
    add_user_message,
    add_assistant_message,
    text_from_message,
)

messages: list[MessageParam] = []

while True:
    user_input = input("> ")

    if user_input == "exit":
        break

    add_user_message(messages, user_input)

    result = chat(messages)
    add_assistant_message(messages, result)
    print(f"\n{text_from_message(result)}\n")
