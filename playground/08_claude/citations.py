import base64
from pathlib import Path
from anthropic.types import (
    MessageParam,
    TextBlock,
    TextCitation,
    CitationPageLocation,
    CitationCharLocation,
)
from ..common.chat import chat, add_user_message
from ..common.renderer import print_usage

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
            "title": "test.pdf",
            "citations": {"enabled": True},
        },
        {"type": "text", "text": "Summarize the key points of this document."},
    ],
)

response = chat(messages)
print_usage(response)

citations: list[TextCitation] = []

for block in response.content:
    if not isinstance(block, TextBlock):
        continue

    if block.citations is None:
        print(block.text, end="")
        continue

    print(block.text, end="")

    for citation in block.citations:
        if citation not in citations:
            citations.append(citation)
        index = citations.index(citation) + 1
        print(f"[{index}]", end="")

print()
print("\n--- References ---")

for i, citation in enumerate(citations, 1):
    cited_text = " ".join(citation.cited_text.split())[:80] + "..."
    match citation:
        case CitationPageLocation():
            pages = f"p.{citation.start_page_number}"
            if citation.end_page_number != citation.start_page_number:
                pages = f"p.{citation.start_page_number}-{citation.end_page_number}"
            print(f'[{i}] ({pages}) "{cited_text}"')
        case CitationCharLocation():
            print(
                f'[{i}] (char {citation.start_char_index}-{citation.end_char_index}) "{cited_text}"'
            )
