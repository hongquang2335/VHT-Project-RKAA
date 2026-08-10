from __future__ import annotations

from collections.abc import Iterable


def normalize_station_ids(station_ids: Iterable[str]) -> list[str]:
    """Chuẩn hóa danh sách trạm: bỏ khoảng trắng, bỏ rỗng và bỏ trùng."""
    normalized: list[str] = []
    seen: set[str] = set()

    for station_id in station_ids:
        if not isinstance(station_id, str):
            raise TypeError(
                f"station_id phải là str, nhận được {type(station_id).__name__}"
            )

        value = station_id.strip()
        if not value:
            continue

        if value not in seen:
            normalized.append(value)
            seen.add(value)

    return normalized
