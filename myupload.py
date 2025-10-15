#!/usr/bin/env python3
import os
import sys
import argparse
import mimetypes
from pathlib import Path
from typing import Iterable, List, Tuple
from contextlib import ExitStack

import requests
from dotenv import load_dotenv

ALLOWED_EXTS = {".xls", ".xlsx", ".xlsm", ".xlsb"}  # adjust if needed
EXCEL_TEMP_PREFIX = "~$"  # Excel lock/temp files

def human_bytes(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"

def validate_token(token: str) -> None:
    if not token or len(token) != 32:
        raise ValueError("UPLOAD_TOKEN must be exactly 32 characters.")

def iter_excel_files(folder: Path) -> Iterable[Path]:
    for p in folder.rglob("*"):
        if not p.is_file():
            continue
        if p.name.startswith(EXCEL_TEMP_PREFIX):
            continue
        if p.suffix.lower() in ALLOWED_EXTS:
            yield p

def pack_batches_by_size(files: List[Path], max_batch_mb: float) -> List[List[Path]]:
    """
    Greedy packer to keep each request under a target size.
    This helps avoid 413 Request Entity Too Large on the server.
    """
    max_bytes = int(max_batch_mb * 1024 * 1024)
    batches: List[List[Path]] = []
    current: List[Path] = []
    current_size = 0

    for f in files:
        try:
            sz = f.stat().st_size
        except FileNotFoundError:
            continue
        # If a single file exceeds max, send it alone
        if sz > max_bytes:
            if current:
                batches.append(current)
                current = []
                current_size = 0
            batches.append([f])
            continue

        if current_size + sz <= max_bytes:
            current.append(f)
            current_size += sz
        else:
            if current:
                batches.append(current)
            current = [f]
            current_size = sz

    if current:
        batches.append(current)
    return batches

def post_batch(session: requests.Session, url: str, batch: List[Path], timeout: int) -> Tuple[bool, dict]:
    """
    Send one multipart request with multiple files field 'files'.
    Returns (ok, response_json_or_error_dict).
    Ensures file handles are closed.
    """
    with ExitStack() as stack:
        files_payload = []
        for p in batch:
            mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            fh = stack.enter_context(open(p, "rb"))
            files_payload.append(("files", (p.name, fh, mime)))

        try:
            resp = session.post(url, files=files_payload, timeout=timeout)
        except requests.RequestException as e:
            return False, {"error": f"request failed: {e}"}

    try:
        data = resp.json()
    except ValueError:
        data = {"error": f"non-JSON response", "status_code": resp.status_code, "text": resp.text[:500]}

    ok = resp.ok and isinstance(data, dict) and data.get("status") in {"ok", "success"} or resp.status_code in (200, 201)
    return ok, data

def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Bulk upload Excel files to the Flask upload API.")
    parser.add_argument("--dir", default=os.getenv("EXCEL_DIR", "./data"), help="Folder containing Excel files")
    parser.add_argument("--url", default=os.getenv("UPLOAD_API_BASE", "http://localhost:5000"), help="API base URL (no trailing slash)")
    parser.add_argument("--token", default=os.getenv("UPLOAD_TOKEN", ""), help="32-char upload token")
    parser.add_argument("--max-batch-mb", type=float, default=float(os.getenv("MAX_BATCH_MB", "40")), help="Target max size (MB) per request")
    parser.add_argument("--timeout", type=int, default=int(os.getenv("REQUEST_TIMEOUT", "300")), help="Request timeout (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="List files and planned batches without uploading")
    args = parser.parse_args()

    try:
        validate_token(args.token.strip())
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(2)

    folder = Path(args.dir).resolve()
    if not folder.exists():
        print(f"[ERROR] Folder not found: {folder}", file=sys.stderr)
        sys.exit(2)

    files = sorted(iter_excel_files(folder))
    if not files:
        print(f"[INFO] No Excel files found under: {folder}")
        return

    # Build upload URL: /upload/{token}
    url = f"{args.url.rstrip('/')}/upload/{args.token}"
    print(f"[INFO] Upload URL: {url}")
    print(f"[INFO] Found {len(files)} files in {folder}")

    # Pack batches by size to avoid 413s
    batches = pack_batches_by_size(files, args.max_batch_mb)
    total_bytes = sum(p.stat().st_size for p in files if p.exists())
    print(f"[INFO] Total size: {human_bytes(total_bytes)} across {len(batches)} batch(es) (target {args.max_batch_mb} MB per batch)")

    for i, batch in enumerate(batches, 1):
        batch_bytes = sum(p.stat().st_size for p in batch if p.exists())
        print(f"  - Batch {i}: {len(batch)} files, {human_bytes(batch_bytes)}")

    if args.dry_run:
        print("[DRY RUN] No uploads performed.")
        return

    # Upload
    session = requests.Session()
    all_saved: List[str] = []
    all_skipped: List[dict] = []

    for i, batch in enumerate(batches, 1):
        print(f"[UPLOAD] Batch {i}/{len(batches)} …")
        ok, data = post_batch(session, url, batch, timeout=args.timeout)

        if not ok:
            print(f"[ERROR] Batch {i} failed: {data}", file=sys.stderr)
            # Fall back to one-by-one uploads for this batch
            print(f"[RETRY] Sending files one-by-one for batch {i} …")
            for p in batch:
                ok1, data1 = post_batch(session, url, [p], timeout=args.timeout)
                if ok1:
                    saved = data1.get("saved", [])
                    all_saved.extend(saved if isinstance(saved, list) else [])
                    skipped = data1.get("skipped", [])
                    if isinstance(skipped, list):
                        all_skipped.extend(skipped)
                    print(f"  ✓ {p.name} uploaded")
                else:
                    print(f"  ✗ {p.name} failed: {data1}", file=sys.stderr)
                    all_skipped.append({"filename": p.name, "reason": str(data1)})
            continue

        # Aggregate results
        saved = data.get("saved", [])
        skipped = data.get("skipped", [])
        if isinstance(saved, list):
            all_saved.extend(saved)
        if isinstance(skipped, list):
            all_skipped.extend(skipped)

        print(f"[OK] Batch {i} → saved={len(saved)} skipped={len(skipped)}")

    print("\n===== SUMMARY =====")
    print(f"Uploaded (saved): {len(all_saved)}")
    print(f"Skipped/failed  : {len(all_skipped)}")
    if all_skipped:
        for s in all_skipped[:50]:
            print(f"  - {s}")
        if len(all_skipped) > 50:
            print(f"  … {len(all_skipped) - 50} more")

if __name__ == "__main__":
    main()
