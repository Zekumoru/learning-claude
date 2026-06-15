from anthropic.types import ModelParam, MessageParam
from ..common.chat import chat, add_user_message, add_assistant_message

messages: list[MessageParam] = []

add_user_message(messages, "Define quantum computing in one sentence.")

answer = chat(messages)
add_assistant_message(messages, answer)

add_user_message(messages, "Write another sentence.")

answer = chat(messages)

print(answer)
print(messages)
