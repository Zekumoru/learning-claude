from typing import Protocol, Any
from numpy.typing import NDArray
from .embeddings import generate_embedding
import numpy as np
import math
import re


class SearchIndex(Protocol):
    def add_document(self, document: dict[str, Any]) -> None: ...

    def search(
        self, query: str, top_k: int = 5
    ) -> list[tuple[dict[str, Any], float]]: ...


class VectorIndex(SearchIndex):
    def __init__(self) -> None:
        self.vectors: list[NDArray[np.floating]] = []
        self.metadata: list[dict[str, str]] = []

    def add_document(self, document: dict[str, Any]) -> None:
        embedding = generate_embedding(document["content"], input_type="document")
        self.vectors.append(np.array(embedding))
        self.metadata.append(document)

    def search(self, query: str, top_k: int = 5) -> list[tuple[dict[str, Any], float]]:
        query_embedding = generate_embedding(query, input_type="query")
        query_vector = np.array(query_embedding)
        distances: list[tuple[int, float]] = []

        for i, vector in enumerate(self.vectors):
            cosine_sim = np.dot(query_vector, vector) / (
                np.linalg.norm(query_vector) * np.linalg.norm(vector)
            )
            distances.append((i, float(cosine_sim)))

        distances.sort(key=lambda x: x[1], reverse=True)
        top_results = distances[:top_k]

        return [(self.metadata[i], dist) for i, dist in top_results]


class BM25Index(SearchIndex):

    # k1 and b are BM25 tuning parameters.
    # The defaults 1.5 and 0.75 are standard.
    #
    # k1 controls how much term frequency matters
    # (higher = more weight on repeated terms).
    #
    # b controls document length normalization
    # (1.0 = fully normalize, 0.0 = ignore length).
    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.documents: list[dict[str, Any]] = []
        self.doc_tokens: list[list[str]] = []
        self.k1 = k1
        self.b = b

    # Splits text into lowercase words.
    #
    # The regex \w+[\w\-]* keeps hyphenated terms like
    # INC-2023-Q4-011as one token instead of splitting them.
    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"\w+[\w\-]*", text.lower())

    # Stores the metadata and pre-tokenizes the content for faster searching later.
    def add_document(self, document: dict[str, Any]) -> None:
        self.documents.append(document)
        self.doc_tokens.append(self._tokenize(document["content"]))

    def search(self, query: str, top_k: int = 5) -> list[tuple[dict[str, str], float]]:
        query_tokens = self._tokenize(query)
        avg_dl = sum(len(d) for d in self.doc_tokens) / len(self.doc_tokens)
        n = len(self.documents)

        scores: list[tuple[int, float]] = []

        for i, doc_tokens in enumerate(self.doc_tokens):
            score = 0.0
            dl = len(doc_tokens)

            for token in query_tokens:
                # term frequency (tf): how many times this token
                # appears in this document
                # Simply: tf means how many times does a term appear in a document
                tf = doc_tokens.count(token)

                # document frequency (df): how many documents contain this token
                # Simply: df means how rare is a term
                df = sum(1 for d in self.doc_tokens if token in d)

                # inverse document frequency (idf): rare terms (low df) get high
                # idf scores. Common terms (high df) get low scores.
                idf = math.log((n - df + 0.5) / (df + 0.5) + 1)

                # Calculate score with k1 and b
                score += (
                    idf
                    * (tf * (self.k1 + 1))
                    / (tf + self.k1 * (1 - self.b + self.b * dl / avg_dl))
                )

            scores.append((i, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [(self.documents[i], s) for i, s in scores[:top_k]]
