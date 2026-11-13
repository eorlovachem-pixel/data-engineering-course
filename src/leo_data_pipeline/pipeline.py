"""Orchestrate extract -> transform -> load -> reports."""

from __future__ import annotations

import json
from pathlib import Path

from .extract import download_google_drive, read_raw_csv
from .load import load_sqlite
from .transform import transform
from .visualize import save_figures


def run_pipeline(
    input_path: str | Path = "data/raw/leo_passes_2026.csv",
    db_path: str | Path = "data/processed/leo_passes.sqlite",
    output_path: str | Path = "data/processed/cleaned_contacts.csv",
    reports_dir: str | Path = "reports",
    drive_id: str | None = None,
) -> dict:
    """Run locally or download the entire raw CSV from Google Drive first."""
    input_path, output_path, reports_dir = Path(input_path), Path(output_path), Path(reports_dir)
    if drive_id:
        download_google_drive(drive_id, input_path)
    raw = read_raw_csv(input_path)
    cleaned, report = transform(raw)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(output_path, index=False, encoding="utf-8")
    load_report = load_sqlite(cleaned, db_path)
    reports_dir.mkdir(parents=True, exist_ok=True)

    summary = cleaned.groupby("station_name", observed=True).agg(
        contacts=("event_id", "count"),
        success_rate=("usable_pass", "mean"),
        mean_snr_db=("snr_db", "mean"),
        transmitted_gb=("transferred_gb", "sum"),
    ).reset_index()
    summary.to_csv(reports_dir / "summary.csv", index=False)
    figures = save_figures(cleaned, reports_dir / "figures")
    report.update({"storage": load_report, "figures": [str(p) for p in figures]})
    (reports_dir / "quality_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report
