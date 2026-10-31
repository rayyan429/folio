"""Step 1 of the pipeline: turn a PDF into a list of text chunks.

For slide decks, one slide = one chunk is a natural split. A slide is short
(well under the embedding model's ~256-token limit) and usually covers one idea.
"""
from pathlib import Path

from pypdf import PdfReader


class UnreadableFile(Exception):
    """Raised for files we can't pull text from. These go on the "Unsorted" list."""


def extract_chunks(path: Path) -> list[str]:
    if path.suffix.lower() != ".pdf":
        raise UnreadableFile(f"{path.name}: not a PDF")

    reader = PdfReader(path)
    if reader.is_encrypted:
        raise UnreadableFile(f"{path.name}: password-protected")

    pages = [" ".join((p.extract_text() or "").split()) for p in reader.pages]

    #p.extract_text() gets the text of one page
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
