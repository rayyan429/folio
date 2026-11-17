from pathlib import Path
from pydoc import doc

from sentence_transformers import SentenceTransformer
model=SentenceTransformer("all-MiniLM-L6-v2") # uses pre-trained model to convert text into embeddings (vectors)

from sklearn.metrics.pairwise import cosine_similarity
from folio.extract import extract_chunks
import numpy as np 


def embed_documents(docs : list[dict]) -> np.ndarray: # convert a list of documents into a 2D array of embeddings
    chunks = [chunk for doc in docs for chunk in doc["chunks"]]
    vectors = model.encode(doc["chunks"], normalize_embeddings = True) # normalize to unit length so cosine similarity is just a dot product
    doc_vectors = vectors.mean(axis=0) # average all chunk vectors to get one vector per document
    doc_vectors = doc_vectors / np.linalg.norm(doc_vectors, axis=1, keepdims=True) # normalize to unit length
    return doc_vectors



if __name__ == "__main__":
    

chunks = extract_chunks(Path("data/sample/class19-retrieval.pdf")) 
embeddings=embed_documents([{"chunks": chunks}])
print(embeddings.shape)
similarity=cosine_similarity(embeddings)
print(similarity)
