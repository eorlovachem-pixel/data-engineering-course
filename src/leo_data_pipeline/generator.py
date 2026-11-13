"""Генератор синтетических событий связи с наземными станциями.

Это не записанная орбитальная телеметрия, и ее нельзя использовать для планирования реальных миссий. 
Я специально закладываю в данные пропуски, запятые вместо точек и дубликаты, 
чтобы потом было что очищать на этапе ETL.
"""

from __future__ import annotations

import csv
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Справочник виртуальных наземных станций с их приблизительными координатами (широта, долгота).
STATIONS = {
    "Murmansk": (68.97, 33.08),
    "Moscow": (55.75, 37.62),
    "Novosibirsk": (55.03, 82.92),
    "Yakutsk": (62.03, 129.73),
    "Vladivostok": (43.12, 131.89),
    "Kaliningrad": (54.71, 20.51),
}

# Полный список колонок (схема данных), которые будут записаны в итоговый CSV.
FIELDS = [
    "event_id", "timestamp_utc", "satellite_id", "orbital_plane", "station_name",
    "station_lat_deg", "station_lon_deg", "frequency_ghz", "elevation_deg",
    "slant_range_km", "pass_duration_s", "rain_rate_mm_h", "cloud_cover_pct",
    "tx_power_w", "tx_antenna_gain_dbi", "rx_antenna_gain_dbi", "polarization",
    "mission_priority", "system_temperature_k", "path_loss_db", "snr_db",
    "capacity_mbps", "transferred_gb", "link_status", "operator_note",
]


def make_rows(count: int = 4200, seed: int = 202611) -> list[dict[str, object]]:
    """Создает строки с данными. Воспроизводимость гарантируется фиксированным seed (зерном случайных чисел)."""
    if count < 1:
        raise ValueError("count must be positive")
    rng = random.Random(seed)
    base = datetime(2026, 9, 1, tzinfo=timezone.utc)
    names = list(STATIONS)
    rows: list[dict[str, object]] = []

    for index in range(count):
        station = rng.choice(names)
        lat, lon = STATIONS[station]
        satellite = rng.randrange(1, 17)
        plane = (satellite - 1) // 4 + 1
        time = base + timedelta(seconds=round(index * 575 + rng.uniform(-90, 90)))
        elevation = rng.uniform(6, 82)
        # Наклонная дальность зависит от угла возвышения. Это упрощенная симуляция, а не точная орбитальная механика.
        slant_range = 520 + 1550 * (1 - math.sin(math.radians(elevation))) + rng.uniform(0, 100)
        duration = round(185 + elevation * 7.0 + rng.uniform(-55, 55))
        rain = max(0, rng.gauss(1.1 if station != "Vladivostok" else 2.4, 2.3))
        cloud = min(100, max(0, rng.gauss(48, 26)))
        tx_power = rng.uniform(9, 23)
        tx_gain = rng.uniform(9, 13)
        rx_gain = rng.uniform(28, 34)
        frequency = rng.choice([7.8, 8.0, 8.2, 8.4])
        temp = rng.uniform(280, 410)
        
        # Потери в свободном пространстве по формуле Фрииса (Friis). f - частота в ГГц, distance - расстояние в км.
        path_loss = 92.45 + 20 * math.log10(frequency) + 20 * math.log10(slant_range)
        
        # Дополнительные потери из-за погоды (дождь и низкий угол возвышения).
        weather_loss = 0.3 + 0.14 * rain + max(0, 12 - elevation) * 0.12
        
        # Расчет мощности принимаемого сигнала и уровня шума.
        power_dbw = 10 * math.log10(tx_power)
        received_dbw = power_dbw + tx_gain + rx_gain - path_loss - weather_loss
        noise_dbw = -228.6 + 10 * math.log10(temp) + 10 * math.log10(25_000_000) + 3
        
        # Отношение сигнал/шум (SNR). Если SNR больше 2 дБ, то сеанс успешный.
        snr = received_dbw - noise_dbw
        status = "success" if snr >= 2.0 else "failed"
        
        # Пропускная способность по формуле Шеннона. Для неудачных сеансов она равна нулю.
        capacity = 0.55 * 25 * math.log2(1 + 10 ** (snr / 10)) if status == "success" else 0
        transferred = capacity * duration * rng.uniform(0.64, 0.94) / 8000
        
        row = {
            "event_id": f"LEO-{index + 1:06d}",
            "timestamp_utc": time.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "satellite_id": f"KA-{satellite:02d}",
            "orbital_plane": plane,
            "station_name": station,
            "station_lat_deg": round(lat, 4),
            "station_lon_deg": round(lon, 4),
            "frequency_ghz": frequency,
            "elevation_deg": round(elevation, 3),
            "slant_range_km": round(slant_range, 3),
            "pass_duration_s": duration,
            "rain_rate_mm_h": round(rain, 3),
            "cloud_cover_pct": round(cloud, 2),
            "tx_power_w": round(tx_power, 3),
            "tx_antenna_gain_dbi": round(tx_gain, 3),
            "rx_antenna_gain_dbi": round(rx_gain, 3),
            "polarization": rng.choice(["RHCP", "LHCP"]),
            "mission_priority": rng.choice([1, 1, 2, 2, 3]),
            "system_temperature_k": round(temp, 2),
            "path_loss_db": round(path_loss, 3),
            "snr_db": round(snr, 3),
            "capacity_mbps": round(capacity, 3),
            "transferred_gb": round(transferred, 4),
            "link_status": status,
            "operator_note": rng.choice(["", "", "", "", "nominal", "monitor"]),
        }
        
        # Намеренно вносим дефекты, чтобы на них можно было отработать этап очистки (Transform).
        if index % 47 == 0:
            row["rain_rate_mm_h"] = ""  # пропуск
        elif index % 53 == 0:
            row["rain_rate_mm_h"] = str(row["rain_rate_mm_h"]).replace(".", ",")  # запятая вместо точки
        if index % 59 == 0:
            row["cloud_cover_pct"] = "n/a"  # текстовый маркер вместо числа
        if index % 191 == 0:
            row["elevation_deg"] = -2.0  # физически невозможное значение
        if index % 223 == 0:
            row["rain_rate_mm_h"] = -4  # отрицательный дождь
        rows.append(row)

    # Имитируем повторную отправку события (дубликат), которая иногда случается в реальных системах.
    rows.extend(dict(row) for row in rows[::97])
    rng.shuffle(rows)
    return rows


def generate_dataset(path: str | Path, count: int = 4200, seed: int = 202611) -> Path:
    """Сохраняет сгенерированные данные в CSV-файл по указанному пути."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(make_rows(count=count, seed=seed))
    return destination