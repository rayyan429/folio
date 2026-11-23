"""Step 5 of the pipeline: give each cluster of PDFs a short folder name with an LLM.

How it works:
  name_clusters() takes every cluster at once (each cluster is a list of
  documents) and returns one folder name per cluster, in the same order.

Why all clusters in one request: if two clusters were both about machine
learning, one on embeddings and one on agents, naming them separately could
label both folders "Machine Learning". When the model sees every cluster
together, it can pick names that tell them apart ("Embeddings" vs. "Agents").
It's also a single request, which matters on the free tier.
A document looks like: {"file": "class19-retrieval.pdf", "chunks": ["slide text...", ...]}
"""
import json
import sys

from folio.vision import call_gemini

PROFILE_CHARS = 2000 # max length of one document's profile, so one big deck can't crowd out the others
LINE_CHARS = 90 # max length of one line (slide text often has no periods, so a "sentence" can be a whole slide)
NAME_CHARS = 40 # max length of a folder name

PROMPT = """You are naming folders for a student's lecture files. Each group below is one folder.
Give each group a folder name that says what its files are about.

Rules:
- 1 to 4 words, Title Case, e.g. "Embeddings & Retrieval" or "Kirchhoff's Laws".
- Name the shared topic, not the format: no "Lecture", "Slides", "Notes", course codes, dates or numbers.
- Ignore boilerplate every deck shares (title slides, "Questions / Comments / Concerns?").
- Every name must be different. If two groups are close, name what sets each apart.
"""

def looks_like_words(text : str) -> bool: # False for handwriting junk like "8l mk %52it ~ 6 + 8£"
    letters = sum(c.isalpha() for c in text)
    return letters / max(len(text), 1) > 0.6

def profile_document(doc : dict) -> str: # short text summary of one document, used for naming prompt
    candidates = []
    for chunk in doc["chunks"]:
        first_sentence = chunk.split(". ")[0].strip()[:LINE_CHARS] # slide titles and "Subject: topic" labels come first
        if first_sentence and looks_like_words(first_sentence) and first_sentence not in candidates:
            candidates.append(first_sentence)

    # Too many lines for the cap? Take every 2nd/3rd/... line so the whole deck is covered,
    # not just its first slides. (Image descriptions come last, so they'd be cut off otherwise.)
    max_lines = PROFILE_CHARS // (LINE_CHARS + 3)
    step = max(1, -(-len(candidates) // max_lines)) # -(-a // b) rounds up
    picked = candidates[::step]

    return "\n".join([f"File: {doc['file']}"] + [f"- {line}" for line in picked])

def clean_name(name : str) -> str: # "  \"Graph Theory.\" " -> "Graph Theory"
    name = " ".join(str(name).split()).strip("\"'.:")
    if len(name) > NAME_CHARS: # cut at the last whole word, not mid-word
        cut = name[:NAME_CHARS + 1] # +1 so a word ending exactly at the limit is kept
        name = cut.rsplit(" ", 1)[0] if " " in cut else name[:NAME_CHARS]
    return name.strip()

def make_unique(names : list[str]) -> list[str]: # ["Agents", "Agents"] -> ["Agents", "Agents 2"], in case the model repeats itself
    seen, unique = {}, []
    for name in names:
        seen[name.lower()] = seen.get(name.lower(), 0) + 1
        unique.append(name if seen[name.lower()] == 1 else f"{name} {seen[name.lower()]}")
    return unique

def name_clusters(clusters : list[list[dict]]) -> list[str]: # one folder name per cluster, same order as the input
    if not clusters:
        return []

    groups = []
    for i, cluster in enumerate(clusters, 1):
        profiles = "\n\n".join(profile_document(doc) for doc in cluster)
        groups.append(f"=== Group {i} ({len(cluster)} files) ===\n{profiles}")
    prompt = (PROMPT + "\n" + "\n\n".join(groups) +
              f"\n\nReturn a JSON array of exactly {len(clusters)} strings, one name per group, in order.")

    response = call_gemini([prompt], json_output=True)
    try:
        names = json.loads(response.text)
    except (json.JSONDecodeError, TypeError):
        names = None
    if not isinstance(names, list) or len(names) != len(clusters): # wrong count means we can't tell which name goes with which group
        print("  Naming answer didn't line up with the groups, using placeholder names.", file=sys.stderr)
        names = []

    cleaned = [clean_name(n) for n in names] or [""] * len(clusters)
    cleaned = [name or f"Folder {i}" for i, name in enumerate(cleaned, 1)] # blank answers get a placeholder the user can rename
    return make_unique(cleaned)

if __name__ == "__main__": # names the sample decks end to end: extract -> embed -> cluster -> name
    from pathlib import Path

    from folio.cluster import cluster_documents
    from folio.embeddings import embed_documents
    from folio.extract import extract_chunks

    paths = sorted(Path("data/sample").glob("*.pdf"))
    docs = [{"file": p.name, "chunks": extract_chunks(p)} for p in paths]
    clusters = cluster_documents(docs, embed_documents(docs))
    for name, cluster in zip(name_clusters(clusters), clusters):
        print(f"{name}:", ", ".join(doc["file"] for doc in cluster))
