"""Fetch a CSV from Google Drive or read a local file."""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd
import requests


def extract_drive_id(value: str) -> str:
    """Support bare Drive IDs and the common Google Drive sharing link formats."""
    value = value.strip()
    match = re.search(r"/file/d/([A-Za-z0-9_-]+)", value)
    if match:
        return match.group(1)
    parsed = urlparse(value)
    if parsed.hostname in {"drive.google.com", "docs.google.com"}:
        ids = parse_qs(parsed.query).get("id", [])
        if ids:
            return ids[0]
    if re.fullmatch(r"[A-Za-z0-9_-]{15,}", value):
        return value
    raise ValueError("Expected a Google Drive file ID or a /file/d/... sharing link")


def download_google_drive(file_id_or_url: str, output: str | Path) -> Path:
    """Download a publicly shared CSV. Requires network and link-viewer access."""
    file_id = extract_drive_id(file_id_or_url)
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    with requests.Session() as session:
        with session.get(url, timeout=(10, 60), stream=True) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" in content_type:
                raise ValueError(
                    "Google Drive returned HTML instead of CSV. "
                    "Set access to 'Anyone with the link: Viewer' for the dataset."
                )
            total = 0
            max_bytes = 50_000_000  # Small educational data only; avoid unbounded downloads.
            with target.open("wb") as f:
                for chunk in response.iter_content(chunk_size=65536):
                    total += len(chunk)
                    if total > max_bytes:
                        target.unlink(missing_ok=True)
                        raise ValueError("Dataset larger than 50 MB download safety limit")
                    f.write(chunk)
    if not target.exists() or target.stat().st_size == 0:
        raise ValueError("Downloaded file is empty")
    header = target.open("rb").read(120)
    if b"<html" in header.lower() or b"<!doctype" in header.lower():
        target.unlink(missing_ok=True)
        raise ValueError("Drive download is an HTML page, not a public CSV")
    return target


def read_raw_csv(input_path: str | Path) -> pd.DataFrame:
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    if path.stat().st_size == 0:
        raise ValueError("CSV file is empty")
    return pd.read_csv(path, dtype={"event_id": "string"}, low_memory=False)


def configured_drive_file_id() -> str | None:
    return os.environ.get("GOOGLE_DRIVE_FILE_ID")
