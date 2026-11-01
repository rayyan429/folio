# Folio test cases

How we check that Folio sorts files correctly, and that it admits failure when it can't.

Any file the system can't read or place goes on an **Unsorted** list instead of being forced into a folder.

## Setup

Lecture PDFs aren't committed, because course material isn't ours to publish. Drop them into the matching `tests/cases/<id>/` folder on your machine. Each case's machine-readable definition is in [`cases.json`](cases.json).

| Folder | Files needed |
|---|---|
| `01_backprop_gradient_descent` | 2+ PDFs: one on backpropagation, one on gradient descent |
| `02_ac_circuits_complex` | AC circuits slides + a complex numbers review PDF |
| `03_two_english_one_spanish` | 2 English PDFs on one topic + 1 Spanish PDF |
| `04_non_english` | 2+ non-English PDFs |
| `05_html_files` | None, already included |

## Component tests

These check the early steps (text extraction and input validation) on their own.

| # | Input | Expected output | What it tests |
|---|---|---|---|
| 1 | PDFs on backpropagation and gradient descent | Sorted together by topic | Basic valid input |
| 2 | AC circuits slides + complex numbers review | Grouped under e.g. "AC Analysis" | Connecting related material that shares few keywords |
| 3 | 2 English PDFs, 1 Spanish | 2 English sorted, Spanish to Unsorted | Partially valid input |
| 4 | PDFs in another language | All to Unsorted | Right file type, wrong language |
| 5 | 3 HTML files | All to Unsorted | Wrong file type |

## End-to-end tests

These run the full pipeline: extraction, image descriptions, embeddings, clustering, and naming.

| Input | Expected output | What it tests |
|---|---|---|
| 4 CSCE 289 lectures (embeddings, transformers, RAG) | Folders like "Embeddings and Retrieval" and "LLM Functionality" | Basic valid input |
| The same lectures + 2 PDFs on RREF and QR factorization | The above plus a separate "Linear Algebra" folder | Unrelated sets of files |
| The same lectures + a password-protected PDF | The lecture folders; locked PDF goes to Unsorted | Admitting failure |

## Scoring

Results are scored on two things:

- **Grouping:** are the right files together?
- **Naming:** does the folder name describe what's in it?

A person applies the naming rubric, because an exact string match would mark "Embeddings & Retrieval" vs. "Retrieval and Embeddings" as a failure.

## Running a component test

Until the embedding step is rebuilt, run the extraction check on a case folder directly:

```bash
python -c "from pathlib import Path; from folio.extract import extract_chunks, UnreadableFile
for p in sorted(Path('tests/cases/05_html_files').iterdir()):
    try: print(p.name, len(extract_chunks(p)), 'chunks')
    except UnreadableFile as e: print('Unsorted:', e)"
```

Swap in another case folder to run that case.

## Current status

| # | Status |
|---|---|
| 5 | Passes: all three HTML files go to Unsorted |
| 1, 2 | Need PDFs added locally; grouping needs the embedding and clustering steps |
| 3, 4 | Will fail for now: nothing checks a file's language yet |
