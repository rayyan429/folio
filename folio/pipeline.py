"""Connects the pipeline steps: PDFs in, proposed folders out.

How it works:
  1. build_document() runs step 1 (extract.py, slide text) and step 2
     (vision.py, image descriptions) on one PDF and returns one document:
         {"file": "kirchhoff.pdf", "chunks": [slide text..., image descriptions...],
          "warning": None}
     This is the handoff format for step 3 (embeddings).
  2. propose_folders() runs step 3 (embeddings.py), step 4 (cluster.py) and
     step 5 (name.py) on all the documents together and returns the folders:
         [{"name": "Retrieval Augmented Generation", "files": ["class19.pdf", "class20.pdf"]}, ...]
  3. analyze() does both for a list of files and collects anything unreadable
     on an "Unsorted" list instead of crashing.
"""
import sys
from pathlib import Path

from folio.cluster import cluster_documents
from folio.extract import UnreadableFile, extract_chunks
from folio.name import name_clusters
from folio.vision import describe_pdf

def build_document(path : Path, display_name : str = None) -> dict: # raises UnreadableFile for files that go to Unsorted
    chunks = extract_chunks(path)
    warning = None
    try:
        descriptions = [r["description"] for r in describe_pdf(path)]
    except Exception as e: # no API key, network down, quota used up: keep going with the slide text alone
        descriptions, warning = [], f"image descriptions skipped ({type(e).__name__})"
    return {
        "file": display_name or path.name,
        "chunks": chunks + descriptions,
        "warning": warning,
    }

def propose_folders(documents : list[dict]) -> list[dict]: # steps 3-5: documents -> [{"name": ..., "files": [...]}, ...]
    # Avoid loading the embedding model when every uploaded file was unreadable.
    if not documents:
        return []

    from folio.embeddings import embed_documents

    vectors = embed_documents(documents)
    clusters = cluster_documents(documents, vectors)

    try:
        names = name_clusters(clusters)
    except Exception as e:
        print(
            f"  Folder naming failed ({type(e).__name__}); using placeholder names.",
            file=sys.stderr,
        )
        names = [f"Folder {i}" for i in range(1, len(clusters) + 1)]

    return [
        {"name": name, "files": [doc["file"] for doc in cluster]}
        for name, cluster in zip(names, clusters)
    ]

def analyze(files : list[tuple[Path, str]]) -> dict: # files = [(path on disk, name to show the user), ...]
    documents, unsorted, warnings = [], [], []
    for path, name in files:
        try:
            doc = build_document(path, name)
        except UnreadableFile as e:
            unsorted.append({"file": name, "reason": str(e).split(": ", 1)[-1]})
            continue
        documents.append(doc)
        if doc["warning"]:
            warnings.append(f"{name}: {doc['warning']}")
    return {
        "folders": propose_folders(documents),
        "unsorted": unsorted,
        "warnings": warnings,
        "method": "embeddings + clustering, folder names by Gemini",
    }
