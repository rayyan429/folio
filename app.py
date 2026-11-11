"""Folio web app: a Flask REST API plus a JavaScript page in web/.

Routes:
  GET  /             the page (web/index.html)
  POST /api/analyze  upload PDFs, get back proposed folders + an Unsorted list
  POST /api/approve  send back the (possibly edited) folders, get a ZIP sorted into them

Uploads are kept in data/uploads/<job id>/ (data/ is gitignored) so that
/api/approve can build the ZIP from the same files the user uploaded.
Nothing on the user's own disk is moved: they download a sorted copy.

Run it:  python app.py    then open http://127.0.0.1:5000
"""
import io
import re
import uuid
import zipfile
from pathlib import Path

from flask import Flask, jsonify, request, send_file
from werkzeug.utils import secure_filename

from folio.pipeline import analyze

UPLOAD_ROOT = Path("data/uploads")
JOB_ID = re.compile(r"^[0-9a-f]{32}$") # job ids are uuid4().hex, anything else is rejected

app = Flask(__name__, static_folder="web", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024 # 300 MB per upload

def safe_folder_name(name : str) -> str: # folder names come from the user's browser, so clean them before using them as paths
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", str(name)).strip(" .")
    return " ".join(name.split())[:80] or "Untitled"

@app.get("/")
def index():
    return app.send_static_file("index.html")

@app.post("/api/analyze")
def api_analyze():
    uploads = request.files.getlist("files")
    if not uploads:
        return jsonify(error="No files were uploaded."), 400

    job_id = uuid.uuid4().hex
    job_dir = UPLOAD_ROOT / job_id
    job_dir.mkdir(parents=True)

    saved = [] # (path on disk, original name shown to the user)
    for f in uploads:
        stored = secure_filename(f.filename) or "file"
        while (job_dir / stored).exists(): # two uploads with the same name
            stored = "copy-" + stored
        f.save(job_dir / stored)
        saved.append((job_dir / stored, stored))

    result = analyze(saved)
    result["job_id"] = job_id
    return jsonify(result)

@app.post("/api/approve")
def api_approve():
    body = request.get_json(silent=True) or {}
    job_id = str(body.get("job_id", ""))
    if not JOB_ID.match(job_id) or not (UPLOAD_ROOT / job_id).is_dir():
        return jsonify(error="Unknown or expired job. Upload the files again."), 400
    job_dir = UPLOAD_ROOT / job_id
    available = {p.name for p in job_dir.iterdir()} # only files from this upload can go in the ZIP

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder in body.get("folders", []):
            name = safe_folder_name(folder.get("name", ""))
            for file in folder.get("files", []):
                if file in available:
                    zf.write(job_dir / file, f"{name}/{file}")
        for file in body.get("unsorted", []):
            if file in available:
                zf.write(job_dir / file, f"Unsorted/{file}")
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name="folio-sorted.zip")

if __name__ == "__main__":
    app.run(debug=True)
