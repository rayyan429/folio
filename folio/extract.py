"""Step 1 of the pipeline: turn a PDF into a list of text chunks.

For slide decks, one slide = one chunk is a natural split.

This file handles the TEXT on each slide only. Images are pulled out separately
by vision.py, which has Gemini describe them. Both read the same PDF, and the
plan is to combine slide text + image descriptions before embed.py.

It's also the gatekeeper: non-PDFs, broken PDFs, password-protected PDFs, and
scanned PDFs with no text raise UnreadableFile and go on the "Unsorted" list.

Uses PyMuPDF to read PDFs: it's written in C, so it reads a deck with
handwritten notes in well under a second (pypdf took 8 s on the same file).
"""
from pathlib import Path

import pymupdf


class UnreadableFile(Exception):
    """Raised for files we can't pull text from. These go on the "Unsorted" list."""


def extract_chunks(path: Path) -> list[str]:

    if path.suffix.lower() != ".pdf":
        raise UnreadableFile(f"{path.name}: not a PDF")

    try:
        doc = pymupdf.open(path)
    except Exception: # a file named .pdf that isn't really one (half-downloaded, renamed, corrupted)
        raise UnreadableFile(f"{path.name}: not a readable PDF")
    if doc.needs_pass:
        raise UnreadableFile(f"{path.name}: password-protected")

    pages = [" ".join(p.get_text().split()) for p in doc]

    #p.get_text() gets the text of one page
    # can return none for a page with no text 
    # one page for one slide 

    # Lecture decks use "build" slides: the same slide repeated with one more
    # bullet each time (see "This Week" / "Why?" in class19). Keep only the last,
    # most complete version, or that slide gets counted three times.


    # skipping build slides (slides that repeat with slight changes)

    chunks = []
    for i, text in enumerate(pages):
        if not text:
            continue
        next_text = pages[i + 1] if i + 1 < len(pages) else ""
        if next_text.startswith(text):
            continue
        chunks.append(text)

    if not chunks:
        raise UnreadableFile(f"{path.name}: no extractable text (scanned images?)")
    return chunks
