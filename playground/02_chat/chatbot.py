from anthropic.types import MessageParam
from ..common.chat import chat, add_user_message, add_assistant_message

messages: list[MessageParam] = []

while True:
    user_input = input("> ")

    if user_input == "exit":
        break

    add_user_message(messages, user_input)

    answer = chat(messages)
    add_assistant_message(messages, answer)
    print(f"\n{answer}\n")
