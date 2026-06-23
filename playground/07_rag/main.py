from pathlib import Path
from .chunks import chunk_by_section
from .embeddings import generate_embedding
from .search import VectorIndex, BM25Index

report_path = Path(__file__).parent / "report.md"

vector_store = VectorIndex()
bm25_store = BM25Index()


with open(report_path, "r") as f:
    text = f.read()

chunks = chunk_by_section(text)

for chunk in chunks:
    document = {"content": chunk}
    vector_store.add_document(document)
    bm25_store.add_document(document)

prompt = "What happened with INC-2023-Q4-011?"

print("\033[1;36mVector Search Results\033[0m")
for metadata, similarity in vector_store.search(prompt):
    print(f"\033[33m{similarity:.4f}\033[0m\n{metadata["content"][:200]}\n")


print("\n\033[1;36mBM25 Search Results\033[0m")
for metadata, score in bm25_store.search(prompt):
    print(f"\033[33m{score:.4f}\033[0m\n{metadata["content"][:200]}\n")
