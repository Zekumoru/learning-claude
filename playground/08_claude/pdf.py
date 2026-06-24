import base64
from pathlib import Path
from anthropic.types import MessageParam
from ..common.chat import chat, print_usage, add_user_message, text_from_message

pdf_path = Path(__file__).parent / "assets/test.pdf"

with open(pdf_path, "rb") as f:
    file_bytes = base64.standard_b64encode(f.read()).decode("utf-8")

messages: list[MessageParam] = []

add_user_message(
    messages,
    [
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": file_bytes,
            },
        },
        {"type": "text", "text": "Summarize the document in one sentence."},
    ],
)

response = chat(messages)

print_usage(response)

print(text_from_message(response))
