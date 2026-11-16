"""Connects the pipeline steps: PDFs in, proposed folders out.

How it works:
  1. build_document() runs step 1 (extract.py, slide text) and step 2
     (vision.py, image descriptions) on one PDF and returns one document:
         {"file": "kirchhoff.pdf", "chunks": [slide text..., image descriptions...],
          "subjects": ["Electrical engineering", ...]}
     This is the handoff format for step 3 (embeddings).
  2. propose_folders() groups the documents and names each group.
  3. analyze() does both for a list of files and collects anything unreadable
     on an "Unsorted" list instead of crashing.

TEMPORARY: steps 3-5 (embeddings, clustering, naming) aren't built yet, so
propose_folders() is a stand-in that groups documents by the subject area
Gemini put at the start of each image description ("Electrical engineering: ...").
Replace it with the real steps when they're ready; nothing else has to change.
"""
from collections import Counter
from pathlib import Path

from folio.extract import UnreadableFile, extract_chunks
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

def propose_folders(documents : list[dict]) -> list[dict]: # TEMPORARY stand-in for steps 3-5, see the docstring at the top
    groups = {}
    for doc in documents:
        name = Counter(doc["subjects"]).most_common(1)[0][0] if doc["subjects"] else "Other"
        groups.setdefault(name, []).append(doc["file"])
    return [{"name": name, "files": files} for name, files in sorted(groups.items())]

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
        "method": "temporary grouping by subject (clustering not built yet)",
    }
