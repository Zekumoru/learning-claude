# 07 - Retrieval-Augmented Generation (RAG)

A from-scratch RAG pipeline that chunks documents, embeds them with sentence-transformers, stores them in a vector index, and searches using semantic, lexical (BM25), and hybrid (RRF) approaches.

## What is RAG?

RAG lets an LLM answer questions about documents it hasn't seen during training. Instead of feeding the entire document into the prompt, you:

1. Split the document into chunks
2. Convert each chunk into a numerical vector (embedding)
3. When a user asks a question, convert that into a vector too
4. Find the chunks whose vectors are most similar to the question
5. Feed only those relevant chunks to the LLM

## Files

- `chunks.py` — text chunking strategies (by character count, by markdown section)
- `embeddings.py` — sentence-transformers embedding generation (`all-MiniLM-L6-v2`, runs locally)
- `search.py` — `SearchIndex` protocol, `VectorIndex` for semantic search, `BM25Index` for lexical search, `Retriever` for hybrid search via reciprocal rank fusion
- `main.py` — ties it all together: loads a report, chunks it, and runs all three search types
- `report.md` — sample document to search against

## Concepts Learned

### Embeddings

Embeddings are numerical vector representations of text. Similar meanings produce vectors that point in similar directions. We use `sentence-transformers` with the `all-MiniLM-L6-v2` model, which runs locally — no API key needed.

Some embedding APIs (like Voyage AI) support **asymmetric search** via an `input_type` parameter (`"document"` vs `"query"`), which optimizes embeddings differently for content being searched through vs. the search query itself. `sentence-transformers` doesn't have this — same embedding for both sides.

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

### Reciprocal Rank Fusion (RRF) — Hybrid Search

The problem with merging results from vector search and BM25 is that their scores are incompatible — cosine similarity (0.71) and BM25 scores (3.2) can't be compared directly. RRF solves this by throwing away the raw scores and using only **rank positions**.

The formula: `RRF_score(d) = Σ(1 / (k + rank))` for each search system.

- **`k`** (default 60) — a dampening constant. Without it, rank 1 scores 1.0 and rank 2 scores 0.5 — a massive cliff. With k=60, the difference between rank 1 (0.0164) and rank 2 (0.0161) is gentle.
- **Summation across systems** — if a document appears in both vector and BM25 results, its scores add up. A document ranked #2 by both systems beats one ranked #1 by only one system.

RRF rewards **consistent presence across search systems** more than dominating a single one.

### `Protocol` — Python's Interface

`Protocol` from `typing` defines a contract of methods a class must implement — like TypeScript's `interface`. It's purely a type-checking concept with zero runtime effect. With explicit inheritance (`class VectorIndex(SearchIndex)`), the type checker enforces the contract at definition time — if you forget a method or get the signature wrong, it errors immediately.

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
