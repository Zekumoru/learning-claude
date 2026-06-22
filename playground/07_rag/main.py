from pathlib import Path
from .chunks import chunk_by_section
from .embeddings import generate_embedding, VectorIndex
from .search import BM25Index

report_path = Path(__file__).parent / "report.md"

vector_store = VectorIndex()
bm25_store = BM25Index()


with open(report_path, "r") as f:
    text = f.read()

chunks = chunk_by_section(text)

embeddings = generate_embedding(chunks, input_type="document")

for embedding, chunk in zip(embeddings, chunks):
    vector_store.add_vector(embedding, {"content": chunk})
    bm25_store.add_document({"content": chunk})

print(f"Generated {len(embeddings)} embeddings")


prompt = "What happened with INC-2023-Q4-011?"

print("\033[1;36mVector Search Results\033[0m")
user_embedding = generate_embedding(prompt)
results = vector_store.search(user_embedding, top_k=2)
for metadata, similarity in results:
    print(f"{similarity:.4f}\n{metadata["content"][:200]}\n")


print("\n\033[1;36mBM25 Search Results\033[0m")
bm25_results = bm25_store.search(prompt, top_k=3)
for metadata, score in bm25_results:
    print(f"{score:.4f}\n{metadata["content"][:200]}\n")
