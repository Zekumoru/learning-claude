from pathlib import Path
from .chunks import chunk_by_section
from .embeddings import generate_embedding, VectorIndex

report_path = Path(__file__).parent / "report.md"

store = VectorIndex()

with open(report_path, "r") as f:
    text = f.read()

chunks = chunk_by_section(text)

embeddings = generate_embedding(chunks, input_type="document")
for embedding, chunk in zip(embeddings, chunks):
    store.add_vector(embedding, {"content": chunk})

print(f"Generated {len(embeddings)} embeddings")


user_embedding = generate_embedding(
    "What did the software engineering dept do last year?"
)
results = store.search(user_embedding, top_k=2)

for metadata, similarity in results:
    print(f"{similarity:.4f}\n{metadata["content"][:200]}\n")
