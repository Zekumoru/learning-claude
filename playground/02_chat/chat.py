from dotenv import load_dotenv

load_dotenv()

from anthropic import Anthropic
from anthropic.types import ModelParam, MessageParam, TextBlock

model: ModelParam = "claude-sonnet-4-6"
max_tokens = 1024

client = Anthropic()


def add_user_message(messages: list[MessageParam], text: str) -> None:
    messages.append({"role": "user", "content": text})


def add_assistant_message(messages: list[MessageParam], text: str) -> None:
    messages.append({"role": "assistant", "content": text})


def chat(messages: list[MessageParam]) -> str:
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
    )

    first_block = message.content[0]

    if not isinstance(first_block, TextBlock):
        raise TypeError("Expected a text response block")

    return first_block.text


if __name__ == "__main__":
    messages: list[MessageParam] = []

    add_user_message(messages, "Define quantum computing in one sentence.")

    answer = chat(messages)
    add_assistant_message(messages, answer)

    add_user_message(messages, "Write another sentence.")

    answer = chat(messages)

    print(answer)
    print(messages)
