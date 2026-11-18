"""Step 4 of the pipeline: group documents whose embeddings are close together.

How it works:
  cluster_documents() takes the documents and their vectors from embeddings.py
  (row i of vectors belongs to docs[i]) and returns a list of clusters, where
  each cluster is a list of documents. That's the input name_clusters() expects.

Why agglomerative clustering: it doesn't need the number of folders up front.
It starts with every document in its own group and keeps merging the two
closest groups until the closest pair is further apart than DISTANCE_THRESHOLD.
"Distance" here is cosine distance = 1 - cosine similarity, so 0 means same
topic and 1 means unrelated.
"""
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_distances

# Groups further apart than this stay separate folders. Lower = more, smaller folders.
# Tuned on data/sample: the two retrieval lectures are 0.14 apart, unrelated
# lectures 0.49-0.63, so 0.35 sits between them. Re-check with more files.
DISTANCE_THRESHOLD = 0.35

def cluster_documents(docs : list[dict], vectors : np.ndarray, threshold : float = DISTANCE_THRESHOLD) -> list[list[dict]]:
    if len(docs) < 2: # nothing to compare; sklearn needs at least 2 samples
        return [docs] if docs else []

    # Precompute distances instead of metric="cosine": sklearn's cosine metric rejects
    # the zero vectors embed_documents() gives empty documents, while cosine_distances
    # just treats them as unrelated (distance 1) to everything.
    distances = cosine_distances(vectors)
    labels = AgglomerativeClustering(
        n_clusters=None, # let the threshold decide how many folders
        distance_threshold=threshold,
        metric="precomputed",
        linkage="average", # distance between groups = average distance between their members
    ).fit_predict(distances)

    clusters = {}
    for doc, label in zip(docs, labels): # dicts keep insertion order, so clusters come out in file order
        clusters.setdefault(label, []).append(doc)
    return list(clusters.values())

if __name__ == "__main__":
    from pathlib import Path

    from folio.embeddings import embed_documents
    from folio.extract import extract_chunks

    paths = sorted(Path("data/sample").glob("*.pdf"))
    docs = [{"file": p.name, "chunks": extract_chunks(p)} for p in paths]
    for i, cluster in enumerate(cluster_documents(docs, embed_documents(docs)), 1):
        print(f"cluster {i}:", ", ".join(doc["file"] for doc in cluster))
