from pathlib import Path
from anthropic.types import ToolParam
from ..chunks import chunk_by_section
from ..search import VectorIndex, BM25Index, Retriever

rag_search_schema: ToolParam = {
    "name": "rag_search",
    "description": (
        "Search through a file using hybrid search (semantic + lexical). "
        "Use this for large files instead of reading them directly. "
        "Automatically indexes the file on first use and caches it for subsequent queries."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path to the file to search.",
            },
            "query": {
                "type": "string",
                "description": "The search query.",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return. Defaults to 5.",
            },
            "truncation": {
                "type": "integer",
                "description": "Maximum characters per result. Defaults to 500.",
            },
        },
        "required": ["path", "query"],
    },
}

_cache: dict[str, Retriever] = {}


def _get_retriever(file_path: Path) -> Retriever:
    key = str(file_path)

    if key in _cache:
        return _cache[key]

    text = file_path.read_text(encoding="utf-8")
    chunks = chunk_by_section(text)

    retriever = Retriever(VectorIndex(), BM25Index())

    for chunk in chunks:
        retriever.add_document({"content": chunk})

    _cache[key] = retriever
    return retriever


def rag_search(
    path: str, query: str, top_k: int = 5, truncation: int = 500, root: Path = Path.cwd()
) -> list[dict[str, str | float]] | dict[str, str]:
    file_path = (root / Path(path)).resolve()

    if not file_path.is_relative_to(root.resolve()):
        return {"error": f"Access denied. Path must be within {root}"}

    if not file_path.is_file():
        return {"error": f"File not found: {path}"}

    retriever = _get_retriever(file_path)
    results = retriever.search(query, top_k=top_k)

    return [
        {"content": doc["content"][:truncation], "score": round(score, 4)}
        for doc, score in results
    ]
