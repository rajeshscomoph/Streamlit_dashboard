import os
import time
from pathlib import Path
from typing import List

from flask import Flask, request, jsonify, abort
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# ----- Config -----
load_dotenv()

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./data")).resolve()
UPLOAD_TOKEN = os.getenv("UPLOAD_TOKEN", "").strip()
MAX_CONTENT_LENGTH_MB = float(os.getenv("MAX_CONTENT_LENGTH_MB", "50"))  # per request
ALLOWED_EXTENSIONS = {".xls", ".xlsx", ".xlsm", ".xlsb"}  # Excel types

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = int(MAX_CONTENT_LENGTH_MB * 1024 * 1024)

# Create upload dir on startup
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def is_valid_token(token: str) -> bool:
    return len(token) == 32 and token == UPLOAD_TOKEN

def allowed_ext(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS

def uniquify(dest_dir: Path, filename: str) -> Path:
    """
    Ensure we don't overwrite files: add epoch millis if file exists.
    """
    base = Path(secure_filename(filename))
    stem, suffix = base.stem, base.suffix
    candidate = dest_dir / base.name
    if not candidate.exists():
        return candidate
    ts = int(time.time() * 1000)
    return dest_dir / f"{stem}-{ts}{suffix}"

@app.errorhandler(413)
def too_large(_e):
    return jsonify(error="Request entity too large"), 413

@app.post("/upload/<token>")
def upload_files(token: str):
    # 1) Auth via 32-char token in path
    if not is_valid_token(token):
        abort(401, description="Invalid or missing 32-character upload token")

    # 2) Read files from multipart form field "files"
    if "files" not in request.files:
        abort(400, description="No files part in request. Use form field 'files'")

    files: List = request.files.getlist("files")
    if not files:
        abort(400, description="No files provided")

    saved, skipped = [], []
    for f in files:
        filename = f.filename or ""
        if not filename:
            skipped.append({"filename": filename, "reason": "empty filename"})
            continue
        if not allowed_ext(filename):
            skipped.append({"filename": filename, "reason": "extension not allowed"})
            continue

        # Build destination path (no uniquify — we overwrite)
        safe_name = secure_filename(filename)
        dest = (UPLOAD_DIR / safe_name)
        tmp_dest = dest.with_suffix(dest.suffix + ".uploading")

        try:
            # save to a temp file first
            f.save(tmp_dest)
            # atomically replace any existing file
            os.replace(tmp_dest, dest)  # works on Windows & *nix
            saved.append(str(dest))
        except Exception as e:
            # cleanup temp if present
            try:
                if tmp_dest.exists():
                    tmp_dest.unlink(missing_ok=True)  # Python 3.8+: wrap in try if missing_ok not available
            except Exception:
                pass
            skipped.append({"filename": filename, "reason": f"save/replace failed: {e}"})

    if not saved and skipped:
        return jsonify(status="error", saved=saved, skipped=skipped), 400

    return jsonify(status="ok", saved=saved, skipped=skipped), 201


if __name__ == "__main__":
    # Bind to 0.0.0.0 for server use; change port if you like
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
