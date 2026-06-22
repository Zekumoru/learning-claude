from dotenv import load_dotenv

load_dotenv()

from voyageai.client import Client as VoyageClient
from typing import overload, Literal
import numpy as np
from numpy.typing import NDArray

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


class VectorIndex:
    def __init__(self) -> None:
        self.vectors: list[NDArray[np.floating]] = []
        self.metadata: list[dict[str, str]] = []

    def add_vector(
        self, vector: list[float] | list[int], metadata: dict[str, str]
    ) -> None:
        self.vectors.append(np.array(vector))
        self.metadata.append(metadata)

    def search(
        self, query_vector: list[float] | list[int], top_k: int = 5
    ) -> list[tuple[dict[str, str], float]]:
        query = np.array(query_vector)
        distances: list[tuple[int, float]] = []

        for i, vector in enumerate(self.vectors):
            cosine_sim = np.dot(query, vector) / (
                np.linalg.norm(query) * np.linalg.norm(vector)
            )
            distances.append((i, float(cosine_sim)))

        distances.sort(key=lambda x: x[1], reverse=True)
        top_results = distances[:top_k]

        return [(self.metadata[i], dist) for i, dist in top_results]
