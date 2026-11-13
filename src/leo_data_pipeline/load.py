"""SQLite relational schema and idempotent data loading."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS ground_stations (
    station_name TEXT PRIMARY KEY,
    lat_deg REAL NOT NULL CHECK(lat_deg BETWEEN -90 AND 90),
    lon_deg REAL NOT NULL CHECK(lon_deg BETWEEN -180 AND 180)
);
CREATE TABLE IF NOT EXISTS contacts (
    event_id TEXT PRIMARY KEY,
    timestamp_utc TEXT NOT NULL,
    contact_date TEXT NOT NULL,
    satellite_id TEXT NOT NULL,
    orbital_plane INTEGER NOT NULL,
    station_name TEXT NOT NULL REFERENCES ground_stations(station_name),
    frequency_ghz REAL NOT NULL,
    elevation_deg REAL NOT NULL CHECK(elevation_deg BETWEEN 0 AND 90),
    slant_range_km REAL NOT NULL,
    pass_duration_s INTEGER NOT NULL,
    rain_rate_mm_h REAL NOT NULL CHECK(rain_rate_mm_h >= 0),
    cloud_cover_pct REAL NOT NULL CHECK(cloud_cover_pct BETWEEN 0 AND 100),
    tx_power_w REAL NOT NULL,
    snr_db REAL NOT NULL,
    capacity_mbps REAL NOT NULL,
    transferred_gb REAL NOT NULL,
    link_status TEXT NOT NULL CHECK(link_status IN ('success', 'failed')),
    mission_priority INTEGER NOT NULL,
    rain_class TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contacts_date ON contacts(contact_date);
CREATE INDEX IF NOT EXISTS idx_contacts_station ON contacts(station_name);
CREATE INDEX IF NOT EXISTS idx_contacts_satellite ON contacts(satellite_id);
"""


def load_sqlite(df: pd.DataFrame, db_path: str | Path) -> dict:
    destination = Path(db_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    station_cols = ["station_name", "station_lat_deg", "station_lon_deg"]
    stations = df[station_cols].drop_duplicates("station_name")
    station_rows = list(stations.itertuples(index=False, name=None))
    names = [
        "event_id", "timestamp_utc", "contact_date", "satellite_id", "orbital_plane",
        "station_name", "frequency_ghz", "elevation_deg", "slant_range_km", "pass_duration_s",
        "rain_rate_mm_h", "cloud_cover_pct", "tx_power_w", "snr_db", "capacity_mbps",
        "transferred_gb", "link_status", "mission_priority", "rain_class",
    ]
    records = df[names].copy()
    records["timestamp_utc"] = records["timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    # Convert pandas scalar types to pure Python for sqlite3.
    records = records.astype(object).where(pd.notna(records), None)
    params = [tuple(row) for row in records.itertuples(index=False, name=None)]

    with sqlite3.connect(destination) as db:
        db.executescript(SCHEMA)
        db.executemany(
            "INSERT OR REPLACE INTO ground_stations (station_name, lat_deg, lon_deg) VALUES (?, ?, ?)",
            station_rows,
        )
        fields = ", ".join(names)
        placeholders = ", ".join(["?"] * len(names))
        db.executemany(f"INSERT OR REPLACE INTO contacts ({fields}) VALUES ({placeholders})", params)
        db.commit()
        total = db.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        stations_count = db.execute("SELECT COUNT(*) FROM ground_stations").fetchone()[0]
        fk_errors = db.execute("PRAGMA foreign_key_check").fetchall()
        if fk_errors:
            raise AssertionError(f"Foreign-key integrity violations: {fk_errors}")
    return {"database": str(destination), "contact_count": total, "station_count": stations_count}
