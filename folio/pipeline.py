"""Connects the pipeline steps: PDFs in, proposed folders out.

How it works:
  1. build_document() runs step 1 (extract.py, slide text) and step 2
     (vision.py, image descriptions) on one PDF and returns one document:
         {"file": "kirchhoff.pdf", "chunks": [slide text..., image descriptions...],
          "warning": None, "slides": 13, "figures": 8, "cached": True}
     This is the handoff format for step 3 (embeddings). slides/figures/cached
     are only for the progress display.
  2. propose_folders() runs step 3 (embeddings.py), step 4 (cluster.py) and
     step 5 (name.py) on all the documents together and returns the folders:
         [{"name": "Retrieval Augmented Generation", "files": ["class19.pdf", "class20.pdf"]}, ...]
  3. analyze() does both for a list of files and collects anything unreadable
     on an "Unsorted" list instead of crashing. It can report progress as it
     goes (one event per file, then the grouping stage), which the web app
     shows live, and it adds 2-3 keywords per folder (keywords.py) so users can
     see why files were grouped.
"""
import sys
from pathlib import Path

from folio.cluster import cluster_documents
from folio.extract import UnreadableFile, extract_chunks
from folio.keywords import folder_keywords
from folio.name import name_clusters
from folio.vision import describe_pdf

def build_document(path : Path, display_name : str = None) -> dict: # raises UnreadableFile for files that go to Unsorted
    chunks = extract_chunks(path)
    warning, stats = None, {}
    try:
        descriptions = [r["description"] for r in describe_pdf(path, stats)]
    except Exception as e: # no API key, network down, quota used up: keep going with the slide text alone
        descriptions, warning = [], f"image descriptions skipped ({type(e).__name__})"
    return {
        "file": display_name or path.name,
        "chunks": chunks + descriptions,
        "warning": warning,
        "slides": len(chunks),                                # for the progress display
        "figures": len(descriptions),
        "cached": not warning and stats.get("new", 0) == 0,   # no new Gemini calls were needed
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

def analyze(files : list[tuple[Path, str]], progress = None) -> dict: # files = [(path on disk, name to show the user), ...]
    # progress: optional function called with event dicts, so the web app can show what's happening live:
    #   {"type": "file", "name": ..., "status": "reading" | "done" | "unsorted", ...details}
    #   {"type": "stage", "stage": "grouping"}
    report = progress or (lambda event: None)
    documents, unsorted, warnings = [], [], []
    for path, name in files:
        report({"type": "file", "name": name, "status": "reading"})
        try:
            doc = build_document(path, name)
        except UnreadableFile as e:
            reason = str(e).split(": ", 1)[-1]
            unsorted.append({"file": name, "reason": reason})
            report({"type": "file", "name": name, "status": "unsorted", "reason": reason})
            continue
        documents.append(doc)
        if doc["warning"]:
            warnings.append(f"{name}: {doc['warning']}")
        report({"type": "file", "name": name, "status": "done",
                "slides": doc["slides"], "figures": doc["figures"], "cached": doc["cached"]})

    report({"type": "stage", "stage": "grouping"})
    folders = propose_folders(documents)
    for folder, words in zip(folders, folder_keywords(folders, documents)):
        folder["keywords"] = words
    return {
        "folders": folders,
        "unsorted": unsorted,
        "warnings": warnings,
        "method": "embeddings + clustering, folder names by Gemini",
    }
