from anthropic.types import MessageParam
from ..common.chat import run_conversation, add_user_message

messages: list[MessageParam] = []

print("Chatbot with adaptive thinking. Type 'exit' to quit.\n")

while True:
    user_input = input("\033[36m|:\033[0m ")

    if user_input.strip().lower() == "exit":
        break

    add_user_message(messages, user_input)
    run_conversation(messages, thinking={"type": "adaptive"})
    print()
