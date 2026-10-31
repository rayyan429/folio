# Folio

Sorts a messy folder of PDFs and slide decks into named topic folders.

**Team:** Rayyan Arshad, Nayeel Suleman · CSCE 289, Fall 2026

## The problem

Most students have a downloads folder full of unsorted PDFs and slide decks that piles up faster than anyone organizes it. Filename search misses anything that wasn't named well in the first place.

## Why GenAI

Keyword search can't group documents by what they're about. A slide deck on backpropagation and a PDF on gradient descent belong together even if they share no keywords. Embeddings capture that meaning, and an LLM can look at a group of documents and write a folder name a person would actually use.

**Input:** a folder of unsorted documents (for the demo, lecture PDFs and slide decks from this semester).
**Output:** the same files sorted into named topic folders, e.g. `Embeddings & Retrieval`, `Prompt Engineering`, `Agents`.

## Approach

| Step | What it does | Module | Status |
|---|---|---|---|
| 1 | Extract text from each PDF, one chunk per slide | `folio/extract.py` | ✅ |
| 2 | Embed the chunks with a sentence-transformer, average them into one vector per document | `folio/embed.py` | ✅ |
| 3 | Describe diagrams and charts with a vision model | `folio/vision.py` | planned |
| 4 | Cluster documents by topic using text and image info | `folio/cluster.py` | planned |
| 5 | Have an LLM name each cluster | `folio/name.py` | planned |
| 6 | Propose the folders and let the user review them before files move | — | planned |

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python -m folio.embed path/to/folder
```

This prints a cosine-similarity matrix: 1.0 means identical topic, near 0 means unrelated.

## What could go wrong

- The LLM invents folder names that sound good but don't match the files.
- Topics split or merge differently from run to run.
- Embeddings cluster by **template** rather than topic. Every CSCE 289 deck opens with the same title slide and "Questions / Comments / Concerns?", which could make all the lectures look alike regardless of subject.
- Scale: good results on 20–30 files don't guarantee good results on thousands.

## Test cases

PDFs aren't committed (course material). Drop them into the matching `tests/cases/<id>/` folder locally. Full definitions are in [`tests/cases.json`](tests/cases.json).

### Component tests: extraction + embedding

| # | Input | Expected output | What it tests |
|---|---|---|---|
| 1 | PDFs on backpropagation and gradient descent | Sorted together by topic | Basic valid input |
| 2 | AC circuits slides + complex numbers review | Grouped under e.g. "AC Analysis" | Connecting related material |
| 3 | 2 English PDFs, 1 Spanish | 2 English sorted, Spanish unsorted | Partially valid input |
| 4 | PDFs in another language | Unable to sort | Right file type, wrong language |
| 5 | 2 HTML files | Unable to sort | Wrong file type |

### End-to-end tests: full pipeline

Any file the system can't read or place goes on an **Unsorted** list instead of being forced into a folder.

| Input | Expected output | What it tests |
|---|---|---|
| 4 CSCE 289 lectures (embeddings, transformers, RAG) | Folders like "Embeddings and Retrieval" and "LLM Functionality" | Basic valid input |
| The same lectures + 2 PDFs on RREF and QR factorization | The above plus a separate "Linear Algebra" folder | Unrelated sets of files |
| The same lectures + a password-protected PDF | The lecture folders; locked PDF goes to Unsorted | Admitting failure |

### Scoring

Results are scored on **grouping** (are the right files together?) and **naming** (does the folder name describe its contents?). A human applies the naming rubric, because an exact string match would mark "Embeddings & Retrieval" vs. "Retrieval and Embeddings" as a failure.
