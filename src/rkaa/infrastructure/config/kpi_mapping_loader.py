"""Đọc cấu hình KPI/counter dùng cho bước thu thập MinIO."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from rkaa.domain.data_collector.minio_kpi_normalizer import KPIMappingItem


def _normalize_source_column(value: object, *, context: str) -> str:
    source_column = str(value or "").strip()
    if not source_column:
        raise ValueError(f"{context}: source_column không được rỗng")
    return source_column


def _build_kpi_item(raw: object, *, index: int) -> KPIMappingItem:
    if not isinstance(raw, dict):
        raise ValueError(f"kpis[{index}] phải là mapping")

    source_column = _normalize_source_column(
        raw.get("source_column"),
        context=f"kpis[{index}]",
    )
    unit = str(raw.get("unit", "")).strip()
    direction = str(raw.get("direction_preference", "informational")).strip()

    return KPIMappingItem(
        source_column=source_column,
        canonical_name=source_column,
        unit=unit,
        direction_preference=direction,
        is_counter=False,
    )


def _build_counter_item(raw: object, *, index: int) -> KPIMappingItem:
    if isinstance(raw, str):
        source_column = _normalize_source_column(
            raw,
            context=f"counters[{index}]",
        )
        unit = ""
    elif isinstance(raw, dict):
        source_column = _normalize_source_column(
            raw.get("source_column"),
            context=f"counters[{index}]",
        )
        unit = str(raw.get("unit", "")).strip()
    else:
        raise ValueError(f"counters[{index}] phải là chuỗi hoặc mapping")

    return KPIMappingItem(
        source_column=source_column,
        canonical_name=source_column,
        unit=unit,
        direction_preference="informational",
        is_counter=True,
    )


def load_kpi_mapping(file_path: str | Path) -> list[KPIMappingItem]:
    """Đọc mapping và bắt buộc canonical_name bằng đúng source_column."""

    path = Path(file_path)
    with path.open("r", encoding="utf-8") as handle:
        raw: Any = yaml.safe_load(handle) or {}

    if not isinstance(raw, dict):
        raise ValueError("kpi_mapping.yaml phải có cấu trúc mapping")

    raw_kpis = raw.get("kpis", [])
    raw_counters = raw.get("counters", [])
    if not isinstance(raw_kpis, list):
        raise ValueError("kpis phải là danh sách")
    if not isinstance(raw_counters, list):
        raise ValueError("counters phải là danh sách")

    items = [
        *(_build_kpi_item(item, index=index) for index, item in enumerate(raw_kpis)),
        *(
            _build_counter_item(item, index=index)
            for index, item in enumerate(raw_counters)
        ),
    ]
    if not items:
        raise ValueError("Không có KPI/counter nào trong cấu hình")

    seen: set[str] = set()
    duplicates: list[str] = []
    for item in items:
        if item.source_column in seen:
            duplicates.append(item.source_column)
        seen.add(item.source_column)
    if duplicates:
        raise ValueError(f"source_column bị trùng: {sorted(set(duplicates))}")

    return items
