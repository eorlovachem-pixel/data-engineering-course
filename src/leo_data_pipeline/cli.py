"""CLI: python -m leo_data_pipeline / leo-etl after package installation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .extract import configured_drive_file_id, download_google_drive, read_raw_csv
from .generator import generate_dataset
from .pipeline import run_pipeline
from .transform import transform

DEFAULT_RAW = Path("data/raw/leo_passes_2026.csv")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="leo-etl", description="Synthetic LEO telemetry: reproducible EDA + ETL + SQLite"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="Generate original simulated raw CSV locally")
    generate.add_argument("--output", type=Path, default=DEFAULT_RAW)
    generate.add_argument("--count", type=int, default=4200)
    generate.add_argument("--seed", type=int, default=202611)
    fetch = commands.add_parser("fetch", help="Preload public dataset from Google Drive")
    fetch.add_argument("--file-id", default=configured_drive_file_id())
    fetch.add_argument("--output", type=Path, default=DEFAULT_RAW)
    validate = commands.add_parser("validate", help="Validate a CSV and show data-quality metrics")
    validate.add_argument("--input", type=Path, default=DEFAULT_RAW)
    run = commands.add_parser("run", help="Run extraction, cleaning, SQLite load and figures")
    run.add_argument("--input", type=Path, default=DEFAULT_RAW)
    run.add_argument("--drive-file-id", default=configured_drive_file_id())
    run.add_argument("--db", type=Path, default=Path("data/processed/leo_passes.sqlite"))
    run.add_argument("--output", type=Path, default=Path("data/processed/cleaned_contacts.csv"))
    run.add_argument("--reports-dir", type=Path, default=Path("reports"))
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "generate":
        path = generate_dataset(args.output, count=args.count, seed=args.seed)
        print(f"Synthetic dataset created: {path} ({args.count} base rows + replay duplicates)")
        return
    if args.command == "fetch":
        if not args.file_id:
            raise SystemExit("Provide --file-id <Google Drive ID> or GOOGLE_DRIVE_FILE_ID")
        print(f"Dataset downloaded from Google Drive to {download_google_drive(args.file_id, args.output)}")
        return
    if args.command == "validate":
        _, report = transform(read_raw_csv(args.input))
    else:
        report = run_pipeline(
            input_path=args.input, db_path=args.db, output_path=args.output,
            reports_dir=args.reports_dir, drive_id=args.drive_file_id,
        )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
