from __future__ import annotations

from pathlib import Path

import yaml

from rkaa.domain.data_collector.station_selection import normalize_station_ids


def load_station_ids_from_yaml(path: str | Path) -> list[str]:
    """Đọc danh sách trạm từ YAML mà không dùng database cục bộ."""
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    stations = payload.get("stations", [])
    if not isinstance(stations, list):
        raise ValueError("Trường 'stations' trong YAML phải là một danh sách")

    return normalize_station_ids(stations)
