import base64
from pathlib import Path
from anthropic.types import MessageParam
from ..common.chat import chat, print_usage, add_user_message, text_from_message

image_path = Path(__file__).parent / "assets/test.png"

with open(image_path, "rb") as f:
    images_bytes = base64.standard_b64encode(f.read()).decode("utf-8")

messages: list[MessageParam] = []

add_user_message(
    messages,
    [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": images_bytes,
            },
        },
        {"type": "text", "text": "What do you see in this image?"},
    ],
)

response = chat(messages)

print_usage(response)

print(text_from_message(response))
