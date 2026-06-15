from anthropic.types import MessageParam
from ..common.chat import client, model, max_tokens, add_user_message

messages: list[MessageParam] = []

add_user_message(messages, "Write a 1 sentence description of a fake database.")


def stream_raw():
    stream = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
        stream=True,
    )

    for event in stream:
        print(event)


def stream():
    with client.messages.stream(
        model=model, max_tokens=max_tokens, messages=messages
    ) as stream:
        for text in stream.text_stream:
            print(text, end="")

        final_message = stream.get_final_message()


stream()
