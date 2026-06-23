from dotenv import load_dotenv

load_dotenv()

from voyageai.client import Client as VoyageClient
from typing import overload, Literal

InputType = Literal["query", "document"]

client = VoyageClient()


@overload
def generate_embedding(
    text: str,
    model: str = "voyage-3-large",
    input_type: InputType | None = "query",
) -> list[float] | list[int]: ...


@overload
def generate_embedding(
    text: list[str],
    model: str = "voyage-3-large",
    input_type: InputType | None = "query",
) -> list[list[float]] | list[list[int]]: ...


def generate_embedding(
    text: str | list[str],
    model: str = "voyage-3-large",
    input_type: InputType | None = "query",
) -> list[float] | list[int] | list[list[float]] | list[list[int]]:
    texts = [text] if isinstance(text, str) else text
    result = client.embed(texts, model=model, input_type=input_type)
    if isinstance(text, str):
        return result.embeddings[0]
    return result.embeddings
