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

PROFILE_CHARS = 2000 # max length of one document's profile, so one big deck can't crowd out the others
LINE_CHARS = 90 # max length of one line (slide text often has no periods, so a "sentence" can be a whole slide)

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

def name_clusters(clusters : list[list[dict]]) -> list[str]: # one folder name per cluster, same order as the input
    pass

if __name__ == "__main__":
    doc = {"file": "test.pdf", "chunks": ["Kirchoff's Laws. They form the foundation...",
                                          "Electrical engineering: KVL. The image shows..."]}
    print(profile_document(doc))
