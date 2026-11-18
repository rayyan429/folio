from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from folio.extract import extract_chunks

model=SentenceTransformer("all-MiniLM-L6-v2") # uses pre-trained model to convert text into embeddings (vectors)
DIM = model.get_embedding_dimension() # 384 for MiniLM


def embed_documents(docs : list[dict]) -> np.ndarray: # convert a list of documents into a 2D array of embeddings, one row per document
    doc_vectors = []
    for doc in docs:
        if not doc["chunks"]: # nothing to embed; a zero vector keeps rows lined up with docs and is similar to nothing
            doc_vectors.append(np.zeros(DIM))
            continue
        vectors = model.encode(doc["chunks"], normalize_embeddings = True) # normalize to unit length so cosine similarity is just a dot product
        doc_vector = vectors.mean(axis=0) # average all chunk vectors to get one vector for this document
        doc_vector = doc_vector / np.linalg.norm(doc_vector) # normalize to unit length
        doc_vectors.append(doc_vector)
    return np.array(doc_vectors)



if __name__ == "__main__":
    paths = sorted(Path("data/sample").glob("*.pdf"))
    docs = [{"file": p.name, "chunks": extract_chunks(p)} for p in paths]
    embeddings=embed_documents(docs)
    print(embeddings.shape)
    similarity=cosine_similarity(embeddings)
    for doc, row in zip(docs, similarity):
        print(f"{doc['file']:<24}", " ".join(f"{s:.2f}" for s in row))
