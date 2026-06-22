# 07 - Retrieval-Augmented Generation (RAG)

A from-scratch RAG pipeline that chunks documents, embeds them with Voyage AI, stores them in a vector index, and searches using both semantic and lexical (BM25) approaches.

## What is RAG?

RAG lets an LLM answer questions about documents it hasn't seen during training. Instead of feeding the entire document into the prompt, you:

1. Split the document into chunks
2. Convert each chunk into a numerical vector (embedding)
3. When a user asks a question, convert that into a vector too
4. Find the chunks whose vectors are most similar to the question
5. Feed only those relevant chunks to the LLM

## Files

- `chunks.py` — text chunking strategies (by character count, by markdown section)
- `embeddings.py` — Voyage AI embedding generation + `VectorIndex` for semantic search
- `search.py` — `BM25Index` for lexical search
- `main.py` — ties it all together: loads a report, chunks it, embeds it, and runs both search types
- `report.md` — sample document to search against

## Concepts Learned

### Embeddings and `input_type` (Asymmetric Search)

Voyage AI's `embed()` accepts an `input_type` parameter: `"document"` or `"query"`. This is called **asymmetric search** — the model prepends a hidden prompt before creating the embedding:

- `"document"` — optimized for content being searched *through* (your knowledge base chunks)
- `"query"` — optimized for the thing you're searching *with* (user's question)

This pushes queries and their relevant documents closer together in vector space than they would be with a single embedding type.

### Cosine Similarity

Measures how similar two vectors are by comparing their direction, ignoring magnitude.

```
cosine_sim = dot(a, b) / (norm(a) * norm(b))
```

- **Dot product** `dot(a, b)` — multiply each pair of matching elements and sum: `a1*b1 + a2*b2 + ... + an*bn`. Tells you how much two vectors point in the same direction.
- **Norm** `norm(a)` — the magnitude (length) of a vector: `sqrt(a1^2 + a2^2 + ... + an^2)`.
- Dividing by the norms normalizes the result to a range of -1 to 1. Higher = more similar.

Example with real numbers:

```
query    = [3, 4]
vector_a = [4, 3]       # similar direction
vector_b = [-2, 5]      # different direction

dot(query, vector_a) = 3*4 + 4*3 = 24
norm(query) = sqrt(9+16) = 5
norm(vector_a) = sqrt(16+9) = 5
sim = 24 / (5*5) = 0.96    # very similar

dot(query, vector_b) = -6 + 20 = 14
norm(vector_b) = sqrt(4+25) = 5.39
sim = 14 / (5*5.39) = 0.52  # less similar
```

### numpy and NDArray

numpy converts Python lists into contiguous C-level arrays. Operations like `np.dot()` run in optimized C loops instead of Python's interpreter, making vector math significantly faster. `NDArray[np.floating]` is the type hint for a numpy array of floats.

### BM25 (Best Match 25) — Lexical Search

Semantic search finds conceptually related content but can miss exact term matches (e.g., searching for an incident ID like `INC-2023-Q4-011`). BM25 complements it with text-based matching.

The algorithm scores documents using three components:

- **TF (Term Frequency)** — how many times a query token appears in a document. More occurrences = higher score.
- **DF (Document Frequency)** — how many documents contain the token. Used to calculate IDF.
- **IDF (Inverse Document Frequency)** — `log((n - df + 0.5) / (df + 0.5) + 1)`. Rare terms (low DF) get high IDF; common terms like "the" get near-zero IDF.

The full scoring formula also accounts for **document length normalization** — 3 matches in a short document is more significant than 3 matches in a long one. This is controlled by two tuning parameters:

- `k1` (default 1.5) — how much term frequency matters
- `b` (default 0.75) — how much to penalize long documents (1.0 = full normalization, 0.0 = ignore length)

### Semantic vs. Lexical Search

| | Semantic (Vector) | Lexical (BM25) |
|---|---|---|
| Strength | Understands meaning and context | Finds exact term matches |
| Weakness | Can miss specific identifiers | Doesn't understand synonyms |
| Example | "What did engineering do?" matches the Software Engineering section | "INC-2023-Q4-011" finds sections containing that exact ID |

Hybrid search runs both in parallel and merges results for the best of both worlds.

## Python Typing Concepts

### `@overload` — Smart Return Types

Lets you define multiple signatures so the type checker knows the return type based on the input type:

```python
@overload
def generate_embedding(text: str, ...) -> list[float] | list[int]: ...
@overload
def generate_embedding(text: list[str], ...) -> list[list[float]] | list[list[int]]: ...
```

Pass a `str`, your editor knows you get a single vector. Pass a `list[str]`, it knows you get a list of vectors.

### `Literal` — Constrained String Values

```python
from typing import Literal

InputType = Literal["query", "document"]
```

Restricts a value to specific strings — your editor autocompletes the options. Unlike TypeScript's `"query" | "document" | (string & {})` trick, Python's `Literal` is strict: only those exact values are allowed. `Literal[...] | str` just collapses to `str`.

### `voyageai.Client` Import Issue

The `voyageai` package ships a `py.typed` marker, which enables strict export checking in Pyright. Its `__init__.py` does `from voyageai.client import Client` without the explicit re-export syntax (`as Client`), so Pyright treats it as a private import. Fix: import from the submodule directly:

```python
from voyageai.client import Client as VoyageClient
```
