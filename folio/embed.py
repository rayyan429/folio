"""Step 2 of the pipeline: turn each document into ONE vector.

How it works:
  1. extract.py splits a PDF into slide-sized chunks.
  2. A sentence-transformer turns each chunk into a 384-number vector.
  3. We average those vectors into one document vector.
  4. Cosine similarity between document vectors tells us how related two files are.
     This is the same cosine from Class 19/20, computed over embeddings
     instead of word counts.

Run it:  python -m folio.embed data/sample
"""
import sys
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from folio.extract import UnreadableFile, extract_chunks

# Small, fast, free, English-only. 384-dim output.
MODEL_NAME = "all-MiniLM-L6-v2"


def embed_document(path: Path, model: SentenceTransformer) -> np.ndarray:
    chunks = extract_chunks(path)
    # normalize_embeddings=True makes every vector length 1, so a plain
    # dot product between two of them IS their cosine similarity.
    chunk_vecs = model.encode(chunks, normalize_embeddings=True)
    doc_vec = chunk_vecs.mean(axis=0)
    return doc_vec / np.linalg.norm(doc_vec)


def embed_folder(folder: Path, model: SentenceTransformer):
    """Returns (file names, matrix with one row per file, list of unsorted files)."""
    names, vecs, unsorted = [], [], []
    for path in sorted(p for p in folder.iterdir() if p.is_file()):
        try:
            vecs.append(embed_document(path, model))
            names.append(path.name)
        except UnreadableFile as e:
            unsorted.append(str(e))
    return names, np.array(vecs), unsorted


def main(folder: str) -> None:
    model = SentenceTransformer(MODEL_NAME)
    names, vecs, unsorted = embed_folder(Path(folder), model)

    if names:
        sim = vecs @ vecs.T  # cosine similarity for every pair of files
        width = max(len(n) for n in names)
        print(" " * width, *(f"{i:>6}" for i in range(len(names))))
        for i, name in enumerate(names):
            print(f"{name:<{width}}", *(f"{s:6.2f}" for s in sim[i]), f"  [{i}]")
    else:
        print("No readable files.")

    if unsorted:
        print("\nUnsorted:")
        for reason in unsorted:
            print("  -", reason)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/sample")
