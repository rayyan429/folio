"""Connects the pipeline steps: PDFs in, proposed folders out.

How it works:
  1. build_document() runs step 1 (extract.py, slide text) and step 2
     (vision.py, image descriptions) on one PDF and returns one document:
         {"file": "kirchhoff.pdf", "chunks": [slide text..., image descriptions...],
          "subjects": ["Electrical engineering", ...]}
     This is the handoff format for step 3 (embeddings).
  2. propose_folders() runs step 3 (embeddings.py), step 4 (cluster.py) and
     step 5 (name.py) on all the documents together and returns the folders:
         [{"name": "Retrieval Augmented Generation", "files": ["class19.pdf", "class20.pdf"]}, ...]
  3. analyze() does both for a list of files and collects anything unreadable
     on an "Unsorted" list instead of crashing.

group_by_subject() is the old stand-in for steps 3-5: it groups documents by
the subject area Gemini put at the start of each image description
("Electrical engineering: ..."). propose_folders() returns it until the TODOs
in it are filled in, so the app keeps working in the meantime.
"""
from collections import Counter
from pathlib import Path

from folio.cluster import cluster_documents
from folio.embeddings import embed_documents
from folio.extract import UnreadableFile, extract_chunks
from folio.name import name_clusters
from folio.vision import describe_pdf

def subject_of(description : str) -> str: # "Electrical engineering: Kirchhoff's Voltage Law. ..." -> "Electrical engineering"
    head = description.split(":")[0].strip()
    return head[:1].upper() + head[1:].lower() if 0 < len(head) <= 40 else ""

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
        "subjects": [s for s in map(subject_of, descriptions) if s],
        "warning": warning,
    }

def group_by_subject(documents : list[dict]) -> list[dict]: # old stand-in for steps 3-5, see the docstring at the top
    groups = {}
    for doc in documents:
        name = Counter(doc["subjects"]).most_common(1)[0][0] if doc["subjects"] else "Other"
        groups.setdefault(name, []).append(doc["file"])
    return [{"name": name, "files": files} for name, files in sorted(groups.items())]

def propose_folders(documents : list[dict]) -> list[dict]: # steps 3-5: documents -> [{"name": ..., "files": [...]}, ...]
    # TODO 1: no documents (every upload was unreadable)? Return [] before
    # loading anything; there's nothing to embed.

    # TODO 2 (step 3): vectors = embed_documents(documents)
    #   -> one row per document, row i belongs to documents[i]

    # TODO 3 (step 4): clusters = cluster_documents(documents, vectors)
    #   -> a list of clusters, each a list of document dicts

    # TODO 4 (step 5): names = name_clusters(clusters)
    #   -> one name per cluster, same order
    #   This calls Gemini, so it can fail (no API key, network, quota). Wrap it
    #   in try/except Exception and fall back to names like "Folder 1", "Folder 2"
    #   so the user still gets their groups and can rename them in the review.

    # TODO 5: build the return value. zip(names, clusters) pairs each name with
    # its cluster; the app wants just the file names, not the whole document:
    #   [{"name": name, "files": [doc["file"] for doc in cluster]}, ...]

    return group_by_subject(documents) # TODO 6: delete this line once TODO 5 returns the real folders

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
        "method": "temporary grouping by subject (clustering not built yet)", # TODO 7: change to e.g. "embeddings + clustering, folder names by Gemini"
    }
