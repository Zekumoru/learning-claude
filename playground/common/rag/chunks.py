import re


def chunk_by_char(
    text: str, chunk_size: int = 150, chunk_overlap: int = 20
) -> list[str]:
    chunks: list[str] = []
    start_idx = 0

    while start_idx < len(text):
        end_idx = min(start_idx + chunk_size, len(text))
        chunk_text = text[start_idx:end_idx]
        chunks.append(chunk_text)

        start_idx = end_idx - chunk_overlap if end_idx < len(text) else len(text)

    return chunks


def chunk_by_section(text: str) -> list[str]:
    pattern = r"\n## "
    return re.split(pattern, text)
