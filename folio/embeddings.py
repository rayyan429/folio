from pathlib import Path
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from folio.extract import extract_chunks
model=SentenceTransformer("all-MiniLM-L6-v2")
chunks = extract_chunks(Path("data/sample/class19-retrieval.pdf"))
embeddings=model.encode(chunks)
print(embeddings.shape)
similarity=cosine_similarity(embeddings)
print(similarity)
