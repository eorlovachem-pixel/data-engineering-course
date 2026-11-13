"""Модуль проверки схемы, обработки пропусков и воспроизводимых ETL-преобразований.

Здесь происходит очистка и обогащение данных.
"""

from __future__ import annotations

import math

import pandas as pd

from .generator import FIELDS

# Список колонок, которые по смыслу должны содержать числа.
NUMERIC = [
    "orbital_plane", "station_lat_deg", "station_lon_deg", "frequency_ghz",
    "elevation_deg", "slant_range_km", "pass_duration_s", "rain_rate_mm_h",
    "cloud_cover_pct", "tx_power_w", "tx_antenna_gain_dbi", "rx_antenna_gain_dbi",
    "mission_priority", "system_temperature_k", "path_loss_db", "snr_db",
    "capacity_mbps", "transferred_gb",
]


def transform(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Очищаю, проверяю и обогащаю копию исходной таблицы, не меняя при этом оригинальные данные."""
    missing = sorted(set(FIELDS).difference(raw.columns))
    if missing:
        raise ValueError(f"В CSV не хватает обязательных колонок: {', '.join(missing)}")
    
    df = raw[FIELDS].copy()
    before = len(df)
    
    # Считаю дубликаты и пропуски до начала любых изменений, чтобы потом зафиксировать их в отчете.
    duplicated = int(df.duplicated(subset="event_id", keep="first").sum())
    missing_before = {name: int(df[name].isna().sum()) for name in FIELDS}
    
    # Удаляю повторные события, оставляя первое вхождение.
    df = df.drop_duplicates(subset="event_id", keep="first").copy()
    
    # Привожу даты к единому формату UTC (мировое время).
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")

    # Привожу числа к нужному типу. Если встречаются запятые вместо точек, меняю их.
    for name in NUMERIC:
        s = df[name].astype("string").str.strip().str.replace(",", ".", regex=False)
        df[name] = pd.to_numeric(s, errors="coerce").astype("float64")

    # Убираю лишние пробелы в текстовых колонках.
    for name in ["event_id", "satellite_id", "station_name", "polarization", "link_status"]:
        df[name] = df[name].astype("string").str.strip()

    # Не исправляю молча физически невозможные значения, а сразу отбрасываю их.
    valid = (
        df["event_id"].notna()
        & df["timestamp_utc"].notna()
        & df["satellite_id"].str.fullmatch(r"KA-\d{2}").fillna(False)
        & df["station_name"].notna()
        & df["polarization"].isin(["RHCP", "LHCP"])
        & df["link_status"].isin(["success", "failed"])
        & df["orbital_plane"].between(1, 4)
        & df["mission_priority"].isin([1, 2, 3])
        & df["station_lat_deg"].between(-90, 90)
        & df["station_lon_deg"].between(-180, 180)
        & df["frequency_ghz"].between(1, 40)
        & df["elevation_deg"].between(0, 90)
        & df["slant_range_km"].between(100, 10000)
        & df["pass_duration_s"].between(1, 1800)
        & df["tx_power_w"].between(0.01, 100)
        & df["system_temperature_k"].between(100, 1000)
        & df["capacity_mbps"].ge(0)
        & df["transferred_gb"].ge(0)
    )
    valid = valid.fillna(False)
    rejected = int((~valid).sum())
    df = df.loc[valid].copy()
    if df.empty:
        raise ValueError("Все строки провалили проверку схемы или доменных ограничений")

    # Отбрасываю битые данные датчиков ДО того, как считать медианы для заполнения пропусков.
    weather_valid = (
        (df["rain_rate_mm_h"].isna() | df["rain_rate_mm_h"].ge(0))
        & (df["cloud_cover_pct"].isna() | df["cloud_cover_pct"].between(0, 100))
    )
    rejected_weather = int((~weather_valid).sum())
    df = df.loc[weather_valid].copy()
    if df.empty:
        raise ValueError("Все строки были отброшены из-за ограничений по погоде")

    # Заполняю легитимные пропуски датчиков медианой по конкретной станции (медиана - это серединное значение).
    # Если для станции данных нет, беру глобальную медиану по всем станциям.
    for name in ["rain_rate_mm_h", "cloud_cover_pct"]:
        df[f"{name}_imputed"] = df[name].isna()
        station_median = df.groupby("station_name")[name].transform("median")
        df[name] = df[name].fillna(station_median).fillna(df[name].median())

    # Проверяю физический предел объема переданных данных (он не может быть больше, чем позволяет пропускная способность канала).
    upper_bound = df["capacity_mbps"] * df["pass_duration_s"] / 8000
    volume_valid = df["transferred_gb"] <= upper_bound + 0.001
    rejected_volume = int((~volume_valid).sum())
    df = df.loc[volume_valid].copy()
    
    # Добавляю новые (производные) признаки для дальнейшего анализа.
    df["contact_date"] = df["timestamp_utc"].dt.strftime("%Y-%m-%d")
    df["usable_pass"] = (df["link_status"] == "success").astype("int8")
    df["rain_class"] = pd.cut(
        df["rain_rate_mm_h"], bins=[-0.001, 0.5, 3, math.inf],
        labels=["dry", "moderate", "heavy"],
    ).astype("string")
    
    # Сортирую данные по времени и ID события.
    df = df.sort_values(["timestamp_utc", "event_id"]).reset_index(drop=True)
    for name in ["orbital_plane", "pass_duration_s", "mission_priority"]:
        df[name] = df[name].astype("int64")

    # Собираю итоговый отчет о качестве. В нем фиксирую, сколько строк было на входе, сколько отброшено и почему.
    report = {
        "raw_rows": before,
        "duplicate_event_ids_removed": duplicated,
        "rejected_schema_domain": rejected,
        "rejected_environment": rejected_weather,
        "rejected_volume": rejected_volume,
        "clean_rows": int(len(df)),
        "column_count_raw": len(FIELDS),
        "unique_event_ids_ratio": float(df["event_id"].nunique() / len(df)),
        "initial_missing_by_column": missing_before,
        "initial_missing_rain_fraction": missing_before["rain_rate_mm_h"] / max(before, 1),
        "environment_missing_imputed": {
            name: int(df[f"{name}_imputed"].sum())
            for name in ["rain_rate_mm_h", "cloud_cover_pct"]
        },
        "valid_timestamp_fraction": float(df["timestamp_utc"].notna().mean()),
        "db_ready": bool(df["event_id"].is_unique and not df["timestamp_utc"].isna().any()),
    }
    return df, report