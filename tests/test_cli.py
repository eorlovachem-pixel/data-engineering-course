"""End-to-end CLI regression checks for the installed Python package."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from leo_data_pipeline.cli import main


def test_python_module_help():
    env = os.environ.copy()
    src = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-m", "leo_data_pipeline", "--help"],
        check=False, capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, result.stderr
    assert all(name in result.stdout for name in ["generate", "fetch", "validate", "run"])


def test_cli_generate_validate_run(tmp_path, capsys):
    source = tmp_path / "data" / "raw.csv"
    db = tmp_path / "data" / "output.sqlite"
    csv_out = tmp_path / "data" / "clean.csv"
    reports = tmp_path / "reports"
    main(["generate", "--count", "1200", "--seed", "202611", "--output", str(source)])
    assert source.is_file()
    capsys.readouterr()

    main(["validate", "--input", str(source)])
    stats = json.loads(capsys.readouterr().out)
    assert stats["raw_rows"] > 1200
    assert stats["duplicate_event_ids_removed"] > 0

    main([
        "run", "--input", str(source), "--db", str(db),
        "--output", str(csv_out), "--reports-dir", str(reports),
    ])
    result = json.loads(capsys.readouterr().out)
    assert result["storage"]["contact_count"] == result["clean_rows"]
    assert db.is_file() and csv_out.is_file()
    assert (reports / "quality_report.json").exists()
    assert (reports / "figures" / "02_eda_dashboard.png").exists()


def test_cli_fetch_requires_drive_id():
    with pytest.raises(SystemExit, match="Provide --file-id"):
        main(["fetch", "--file-id", ""])
