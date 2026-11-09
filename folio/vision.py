"""Step 2 of the pipeline: describe the images in a PDF with a vision model.

How it works:
  1. extract_images() reads the whole PDF and collects every embedded image
     (page number, raw bytes, format, a hash used to spot repeats, and the text
     of the slide it's on).
  2. describe_pdf() skips repeated images, checks the cache, and sends the rest
     to Gemini in batches (several images per request), then drops "DECORATIVE"
     answers for logos and other images with no teaching content.

Why the slide text: on its own a circuit drawing is just "a circuit". With the
slide's text ("Use Ohm's Law and Kirchhoff's Law to find R") Gemini names what
is actually being taught instead of guessing.

Why batches: the free tier limits requests per minute, not images, so 6 images
in one request cost the same quota as 1. Results are cached in
data/vision_cache.json, so re-running on the same decks makes no requests.
Changing PROMPT or MODEL automatically invalidates the cache.

Not connected to the embedding step yet. The plan is to add these descriptions
to each document's text chunks before they're embedded.

Run it:  python -m folio.vision [path/to/deck.pdf]   (describes every image)
         python -m folio.vision --demo                (one image, prints prompt/input/output)
"""
# google-gen-ai is Google's gemini library
# pymupdf reads PDFs (text and images); it's written in C, so it's much faster than pypdf

import hashlib
import json
import sys
import time
from pathlib import Path

import pymupdf
from google import genai
from google.genai import errors, types

MODEL = "gemini-3.5-flash-lite" # fast and not overloaded on the free tier (3.8-flash kept returning 503)
THINKING = types.ThinkingConfig(thinking_level="MINIMAL") # describing an image doesn't need much reasoning
BATCH_SIZE = 6 # images per request (smaller batches give each image more attention)
SLIDE_TEXT_CHARS = 600 # how much of the slide's text to send along with its image
CACHE_PATH = Path("data/vision_cache.json") # data/ is gitignored
MIME_TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"} # tells Gemini the image format

PROMPT = """This image comes from a lecture slide. The slide's own text is given with the image for context.
Describe what the image teaches in 2-3 sentences of plain text with no markdown, headings, or bullet points.
Begin with the subject area and the specific topic, for example: "Electrical engineering: Kirchhoff's Voltage Law." or "Machine learning: gradient descent."
Name the specific concepts, laws, methods, or techniques involved using their standard names, because these descriptions are used to group lecture files by topic.
If the image is a graph, say what is being measured and the main trend. If it is a diagram, say what process or system it illustrates.
Ignore handwriting you can't read. Don't mention colors, layout, or people's names.
If the image is only a logo, icon, photo of a person, or decoration with no teaching content, reply with exactly: DECORATIVE"""

PROMPT_VERSION = hashlib.sha1((MODEL + PROMPT).encode()).hexdigest()[:8] # part of the cache key, so editing PROMPT or MODEL gets fresh descriptions

_client = None

def get_client() -> genai.Client: # created the first time it's needed, so importing this file doesn't require an API key
    global _client
    if _client is None:
        _client = genai.Client()
    return _client

def extract_images(path : Path) -> list[dict]: # returns a list of dictionaries, one per image
    doc = pymupdf.open(path)
    images = []
    for page_num, page in enumerate(doc): # every page in the PDF
        slide_text = " ".join(page.get_text().split())[:SLIDE_TEXT_CHARS] # context sent along with the page's images
        for info in page.get_images(full=True): # for every image on a page
            xref = info[0] # the image's id inside the PDF
            img = doc.extract_image(xref) # {"image": raw bytes, "ext": "png" / "jpeg" / ...}
            data, ext = img["image"], img["ext"]
            if ext not in MIME_TYPES: # unusual formats (jpx, tiff, ...) get converted to PNG
                pix = pymupdf.Pixmap(doc, xref)
                if pix.n - pix.alpha >= 4: # CMYK images have to become RGB before saving as PNG
                    pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                data, ext = pix.tobytes("png"), "png"
            images.append({
                "page": page_num + 1,  # page numbers are 1-indexed
                "data": data,
                "mime": MIME_TYPES[ext],
                "hash": hashlib.sha1(data).hexdigest(), # same bytes = same image, so repeats are described once
                "slide_text": slide_text,
            })
    return images

def call_gemini(contents : list, json_output : bool = False, tries : int = 5): # one request, retried if Gemini is busy
    config = types.GenerateContentConfig(
        thinking_config=THINKING,
        response_mime_type="application/json" if json_output else None,
    )
    for attempt in range(tries):
        try:
            return get_client().models.generate_content(model=MODEL, contents=contents, config=config)
        except errors.APIError as e:
            if e.code not in (429, 500, 503) or attempt == tries - 1: # only quota and server errors are worth retrying
                raise
            wait = 15 * (attempt + 1) # 429 = per-minute quota used up, so wait it out
            print(f"  Gemini returned {e.code}, retrying in {wait}s...", file=sys.stderr)
            time.sleep(wait)

def image_part(image : dict) -> types.Part:
    return types.Part.from_bytes(data=image["data"], mime_type=image["mime"])

def slide_context(image : dict) -> str:
    return f"Slide text: {image['slide_text'] or '(none)'}"

def describe_image(image : dict) -> str: # sends one image + its slide text + the prompt to Gemini, returns its description
    return call_gemini([slide_context(image), image_part(image), PROMPT]).text.strip()

def describe_batch(images : list[dict]) -> list[str]: # sends several images in ONE request, returns one description per image
    parts = []
    for i, im in enumerate(images, 1): # each image is preceded by its own slide's text
        parts += [f"Image {i}. {slide_context(im)}", image_part(im)]
    parts.append(f"Apply these rules to EACH of the {len(images)} images separately:\n{PROMPT}\n\n"
                 f"Return a JSON array of exactly {len(images)} strings, one per image, in the same order.")
    response = call_gemini(parts, json_output=True)
    try:
        descriptions = json.loads(response.text)
    except (json.JSONDecodeError, TypeError):
        descriptions = None
    if not isinstance(descriptions, list) or len(descriptions) != len(images): # wrong count means we can't trust the order
        print("  Batch answer didn't line up with the images, describing them one at a time.", file=sys.stderr)
        return [describe_image(im) for im in images]
    return [str(d).strip() for d in descriptions]

def load_cache() -> dict:
    return json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}

def save_cache(cache : dict):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=1))

def describe_pdf(path : Path) -> list[dict]: # every useful image in the PDF -> [{"page": 4, "description": "..."}]
    images = extract_images(path)
    cache = load_cache()

    key = lambda im: f"{PROMPT_VERSION}:{im['hash']}" # same image + same prompt/model = reuse the saved description

    unique = {} # cache key -> image, keeps the first copy of each repeated image
    for im in images:
        unique.setdefault(key(im), im)
    todo = [im for k, im in unique.items() if k not in cache]

    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i + BATCH_SIZE]
        for im, desc in zip(batch, describe_batch(batch)):
            cache[key(im)] = desc
        save_cache(cache) # saved after every batch, so a crash halfway doesn't lose finished work

    results, seen = [], set()
    for im in images:
        desc = cache[key(im)]
        if im["hash"] in seen or desc.upper().startswith("DECORATIVE"): # skip repeats and logos
            continue
        seen.add(im["hash"])
        results.append({"page": im["page"], "description": desc})
    return results

def demo(): # one image with the prompt, input, and output printed (the "working piece" for the update)
    pdf = Path("data/sample/class17-images.pdf")
    image = extract_images(pdf)[0] # first image in the deck

    out = Path("data/demo_input.png") # saved so it can be shown in the update
    out.write_bytes(image["data"])

    print("PROMPT:\n", PROMPT)
    print(f"\nINPUT: {pdf.name}, page {image['page']} (saved to {out})")
    print("\nOUTPUT:\n", describe_image(image))

if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo()
    else:
        pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/sample/class19-retrieval.pdf")
        start = time.time()
        results = describe_pdf(pdf)
        for r in results:
            print(f"page {r['page']}: {r['description']}\n")
        print(f"{len(results)} useful image descriptions from {pdf.name} in {time.time() - start:.1f}s")