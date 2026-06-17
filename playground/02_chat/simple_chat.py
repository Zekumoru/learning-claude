from anthropic.types import ModelParam, MessageParam
from ..common.chat import (
    chat,
    add_user_message,
    add_assistant_message,
    text_from_message,
)

messages: list[MessageParam] = []

add_user_message(messages, "Define quantum computing in one sentence.")

result = chat(messages)
add_assistant_message(messages, result)

add_user_message(messages, "Write another sentence.")

result = chat(messages)

print(text_from_message(result))
print(messages)
