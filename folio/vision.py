"""Step 3 of the pipeline: describe the images in a PDF with a vision model.

How it works:
  1. extract_images() reads the whole PDF and collects every embedded image
     (page number, filename, raw bytes).
  2. describe_image() sends one image plus PROMPT to Gemini and returns a short
     plain-text description of what it teaches, or "DECORATIVE" for logos etc.

Not connected to embed.py yet. The plan is to add these descriptions to each
document's text chunks before they're embedded.

Run it:  python -m folio.vision
(demo: describes the first image in class17-images.pdf and saves it to data/demo_input.png)
"""
# google-gen-ai is Google's gemini library
# pillow is an image processing library
# pypdf is a library for reading PDF files and it needs pillow to pull images out of PDFs

from pathlib import Path
from google import genai
from google.genai import types
from pypdf import PdfReader

client = genai.Client() # created once and reused for every image
MODEL = "gemini-3.8-flash"
MIME_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"} # tells Gemini the image format

PROMPT = """This image comes from a lecture slide. Describe what it is teaching, in 2-3 sentences of plain text with no markdown, headings, or bullet points.
Start by naming the subject area and topic (for example: "Machine learning: gradient descent").
If the image is a graph, say what is being measured and the main trend.
If the image is a diagram, say what process or system it illustrates.
If the image is a screenshot, say what kind of content it shows and what it is about.
Focus on concepts, not names, numbers, or visual details like colors and layout.
If the image is only a logo, icon, photo of a person, or decoration with no teaching content, reply with exactly: DECORATIVE"""

def extract_images(path : Path) -> list[dict]: # returns a list of dictionaries, one per image
    reader = PdfReader(path)
    images = []
    for page_num, page in enumerate(reader.pages): # reader.pages is for every page in the PDF
        for img in page.images: # for every image on a page
            images.append({
                "page": page_num + 1,  # page numbers are 1-indexed
                "name": img.name,
                "data": img.data    # raw image bytes, can be saved to a file or processed further
            })
    return images

def describe_image(image : dict) -> str: # sends one image + the prompt to Gemini, returns its description
    suffix = Path(image["name"]).suffix.lower() # "Im1.png" -> ".png"
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=image["data"], mime_type=MIME_TYPES[suffix]),
            PROMPT,
        ],
    )
    return response.text

if __name__ == "__main__":
    pdf = Path("data/sample/class17-images.pdf")
    image = extract_images(pdf)[0] # first image in the deck

    out = Path("data/demo_input.png") # saved so it can be shown in the update
    out.write_bytes(image["data"])

    print("PROMPT:\n", PROMPT)
    print(f"\nINPUT: {pdf.name}, page {image['page']} (saved to {out})")
    print("\nOUTPUT:\n", describe_image(image))