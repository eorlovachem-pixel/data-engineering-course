from __future__ import annotations

import json
import sqlite3

import pandas as pd
import pytest

from leo_data_pipeline.extract import extract_drive_id
from leo_data_pipeline.generator import FIELDS, generate_dataset, make_rows
from leo_data_pipeline.load import load_sqlite
from leo_data_pipeline.pipeline import run_pipeline
from leo_data_pipeline.transform import transform


def test_generated_dataset_unique_and_large_enough():
    data = make_rows(count=1200, seed=33)
    assert len(data) > 1200
    assert len(FIELDS) >= 15
    assert len(set(row["event_id"] for row in data)) == 1200
    assert data == make_rows(count=1200, seed=33)


def test_google_drive_links():
    fid = "1AbcdefGhijk1234567"
    assert extract_drive_id(f"https://drive.google.com/file/d/{fid}/view?usp=sharing") == fid
    assert extract_drive_id(f"https://drive.google.com/uc?export=download&id={fid}") == fid
    with pytest.raises(ValueError):
        extract_drive_id("https://example.com/no-id")


def test_schema_deduplication_and_quality():
    data = pd.DataFrame(make_rows(count=250, seed=4))
    cleaned, report = transform(data)
    assert cleaned["event_id"].is_unique
    assert report["duplicate_event_ids_removed"] > 0
    assert report["rejected_schema_domain"] > 0
    assert report["column_count_raw"] >= 15
    assert "rain_rate_mm_h_imputed" in cleaned
    assert cleaned["elevation_deg"].between(0, 90).all()
    assert cleaned["rain_rate_mm_h"].ge(0).all()
    assert not cleaned["timestamp_utc"].isna().any()
    assert cleaned["transferred_gb"].le(
        cleaned["capacity_mbps"] * cleaned["pass_duration_s"] / 8000 + .001
    ).all()


def test_missing_required_column_rejected():
    raw = pd.DataFrame(make_rows(count=20))
    with pytest.raises(ValueError, match="Missing required"):
        transform(raw.drop(columns=["event_id"]))


def test_full_pipeline_and_sqlite_idempotency(tmp_path):
    source = generate_dataset(tmp_path / "original.csv", count=1200, seed=7)
    kwargs = dict(
        input_path=source, db_path=tmp_path / "result.db",
        output_path=tmp_path / "clean.csv", reports_dir=tmp_path / "reports",
    )
    report = run_pipeline(**kwargs)
    assert report["clean_rows"] > 1000
    assert report["storage"]["contact_count"] == report["clean_rows"]
    assert len(report["figures"]) == 2
    assert all((tmp_path / "reports" / "figures" / p).exists() for p in [
        "01_downlink_by_station.png", "02_eda_dashboard.png"
    ])
    assert json.loads((tmp_path / "reports" / "quality_report.json").read_text()) == report
    second = run_pipeline(**kwargs)
    assert second["storage"]["contact_count"] == report["clean_rows"]
    with sqlite3.connect(tmp_path / "result.db") as conn:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("SELECT count(*) FROM ground_stations").fetchone()[0] == 6
        assert conn.execute("SELECT count(*) FROM contacts").fetchone()[0] == report["clean_rows"]
        assert conn.execute("SELECT SUM(transferred_gb) FROM contacts").fetchone()[0] > 0


def test_google_drive_preload_downloads_csv_without_real_network(tmp_path, monkeypatch):
    from leo_data_pipeline.extract import download_google_drive

    class FakeResponse:
        headers = {"Content-Type": "text/csv"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size=65536):
            yield b"event_id,value\nLEO-1,123\n"

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, **kwargs):
            assert "drive.google.com/uc?export=download&id=" in url
            assert kwargs["stream"] is True
            return FakeResponse()

    monkeypatch.setattr("leo_data_pipeline.extract.requests.Session", FakeSession)
    output = download_google_drive("https://drive.google.com/file/d/1AbcdefGhijk1234567/view", tmp_path / "input.csv")
    assert output.read_text() == "event_id,value\nLEO-1,123\n"


def test_google_drive_preload_rejects_private_html(tmp_path, monkeypatch):
    from leo_data_pipeline.extract import download_google_drive

    class FakeResponse:
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def raise_for_status(self):
            pass

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("leo_data_pipeline.extract.requests.Session", FakeSession)
    with pytest.raises(ValueError, match="Anyone with the link"):
        download_google_drive("1AbcdefGhijk1234567", tmp_path / "private.csv")
