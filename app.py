"""Folio web app: a Flask REST API plus a JavaScript page in web/.

Routes:
  GET  /                    the page (web/index.html)
  POST /api/analyze         upload files; starts sorting them in the background and returns a job id
  GET  /api/status/<job>    progress so far (which files are read, which stage), and the result once done
  POST /api/approve         send back the (possibly edited) folders, get a ZIP sorted into them

Why a background job: sorting new decks can take a minute. Instead of one long
request with a spinner, the page polls /api/status every second and shows each
file being read, then the grouping, then the real folders.

Uploads are kept in data/uploads/<job id>/ (data/ is gitignored) so that
/api/approve can build the ZIP from the same files the user uploaded.
Nothing on the user's own disk is moved: they download a sorted copy.

Run it:  python app.py    then open http://127.0.0.1:5000
"""
import io
import re
import threading
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

jobs = {}                  # job id -> progress and result, read by /api/status
jobs_lock = threading.Lock() # the sorting thread writes while requests read

def safe_folder_name(name : str) -> str: # folder names come from the user's browser, so clean them before using them as paths
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", str(name)).strip(" .")
    return " ".join(name.split())[:80] or "Untitled"

def run_job(job_id : str, saved : list): # runs in a background thread, updating jobs[job_id] as it goes
    def on_progress(event : dict):
        with jobs_lock:
            job = jobs[job_id]
            if event["type"] == "file":
                job["files"][event["name"]].update({k: v for k, v in event.items() if k not in ("type", "name")})
            else:
                job["stage"] = event["stage"]
    try:
        result = analyze(saved, progress=on_progress)
        with jobs_lock:
            jobs[job_id].update(stage="done", result=result)
    except Exception as e: # anything unexpected: tell the page instead of leaving it waiting forever
        app.logger.exception("sorting job %s failed", job_id)
        with jobs_lock:
            jobs[job_id].update(stage="error", error=f"Sorting failed ({type(e).__name__}). Try again.")

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

    with jobs_lock:
        jobs[job_id] = {"stage": "reading", "files": {name: {"status": "waiting"} for _, name in saved},
                        "order": [name for _, name in saved], "result": None, "error": None}
    threading.Thread(target=run_job, args=(job_id, saved), daemon=True).start()
    return jsonify(job_id=job_id, files=[name for _, name in saved])

@app.get("/api/status/<job_id>")
def api_status(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            return jsonify(error="Unknown job. Upload the files again."), 404
        return jsonify(
            stage=job["stage"],
            files=[{"name": n, **job["files"][n]} for n in job["order"]], # upload order, so cards don't jump around
            result=job["result"],
            error=job["error"],
        )

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
