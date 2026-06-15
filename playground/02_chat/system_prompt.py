from anthropic.types import MessageParam
from ..common.chat import chat, add_user_message

messages: list[MessageParam] = []

add_user_message(
    messages, "Write a Python function that checks a string for duplicate characters."
)

answer = chat(
    messages=messages,
    system="You are a Python engineer who writes very concise code and does not talk much more than necessary.",
)

print(answer)
