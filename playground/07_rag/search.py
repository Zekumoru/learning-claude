import math
import re


class BM25Index:

    # k1 and b are BM25 tuning parameters.
    # The defaults 1.5 and 0.75 are standard.
    #
    # k1 controls how much term frequency matters
    # (higher = more weight on repeated terms).
    #
    # b controls document length normalization
    # (1.0 = fully normalize, 0.0 = ignore length).
    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.documents: list[dict[str, str]] = []
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
    def add_document(self, metadata: dict[str, str]) -> None:
        self.documents.append(metadata)
        self.doc_tokens.append(self._tokenize(metadata["content"]))

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
