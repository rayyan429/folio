"""Picks 2-3 keywords per folder, so users can see why files were grouped together.

How it works:
  folder_keywords() joins the text of every document in a folder into one
  string per folder, then scores words with TF-IDF: a word scores high when it
  is frequent in this folder but rare in the other folders. So the keywords for
  a circuits folder come out as "voltage", "current", "resistor" rather than
  words every lecture has, like "example".
"""
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

from folio.name import looks_like_words

# Words that show up in almost every lecture deck or image description and say nothing about the topic.
BOILERPLATE = {
    "slide", "slides", "lecture", "lectures", "class", "week", "questions", "comments", "concerns",
    "example", "examples", "figure", "image", "images", "diagram", "shows", "illustrates", "teaches",
    "demonstrates", "university", "department", "texas", "fall", "spring", "summer", "csce", "ecen",
    "https", "http", "www", "com", "org", "edu", "using", "used", "use", "like", "let", "way",
    "cos", "sin", "tan", "exp", "log", "max", "min", # bits of equations, not topics
}
STOP_WORDS = list(ENGLISH_STOP_WORDS | BOILERPLATE)

def folder_keywords(folders : list[dict], documents : list[dict], k : int = 3) -> list[list[str]]: # one keyword list per folder
    if not folders:
        return []
    chunks_by_file = {doc["file"]: doc["chunks"] for doc in documents}
    texts = []
    for folder in folders:
        lines = [c for f in folder["files"] for c in chunks_by_file.get(f, []) if looks_like_words(c)] # skip handwriting junk
        texts.append(" ".join(lines))
    if not any(texts):
        return [[] for _ in folders]

    vectorizer = TfidfVectorizer(
        stop_words=STOP_WORDS,
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z\-]{2,}\b", # words of 3+ letters, no numbers
        ngram_range=(1, 2),                           # allow two-word terms like "power transfer"
        sublinear_tf=True,                            # a word said 50 times isn't 50x as important
    )
    scores = vectorizer.fit_transform(texts).toarray()
    terms = vectorizer.get_feature_names_out()

    keywords = []
    for row in scores:
        picked = []
        for i in row.argsort()[::-1]: # best score first
            if row[i] <= 0 or len(picked) == k:
                break
            term = terms[i]
            words = {w.rstrip("s") for w in term.split()} # "agents" and "agent" count as the same word
            if len(words) < len(term.split()): # "cos cos", "agent agents": the same word twice isn't a phrase
                continue
            if any(words & {w.rstrip("s") for w in p.split()} for p in picked): # skip "kirchhoff law" once "kirchhoff" is in
                continue
            picked.append(term)
        keywords.append(picked)
    return keywords
