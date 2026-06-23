from typing import overload
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")


@overload
def generate_embedding(
    text: str,
) -> list[float]: ...


@overload
def generate_embedding(
    text: list[str],
) -> list[list[float]]: ...


def generate_embedding(
    text: str | list[str],
) -> list[float] | list[list[float]]:
    texts = [text] if isinstance(text, str) else text
    embeddings = model.encode(texts).tolist()
    if isinstance(text, str):
        return embeddings[0]
    return embeddings
