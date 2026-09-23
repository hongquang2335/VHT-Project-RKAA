"""Load FR-303 KPI warning/critical thresholds từ YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from rkaa.domain.threshold_manager import (
    DirectionThreshold,
    KPIThresholdRule,
    ThresholdMode,
    ThresholdManager,
)


def _mapping(value: Any, context: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{context} phải là mapping")
    return value


def _number_or_none(value: Any, context: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context} phải là số hoặc null") from exc


def _direction_threshold(raw: Any, context: str) -> DirectionThreshold:
    payload = _mapping(raw, context)
    mode_value = str(payload.get("mode", "absolute")).strip().lower()
    try:
        mode = ThresholdMode(mode_value)
    except ValueError as exc:
        raise ValueError(f"{context}.mode phải là absolute hoặc percent") from exc
    return DirectionThreshold(
        mode=mode,
        warning=_number_or_none(payload.get("warning"), f"{context}.warning"),
        critical=_number_or_none(payload.get("critical"), f"{context}.critical"),
    )


def load_kpi_threshold_manager(path: str | Path) -> ThresholdManager:
    with Path(path).open("r", encoding="utf-8") as handle:
        root = _mapping(yaml.safe_load(handle) or {}, "root")

    raw_kpis = _mapping(root.get("kpis"), "kpis")
    rules: list[KPIThresholdRule] = []
    for kpi_name, raw in raw_kpis.items():
        payload = _mapping(raw, f"kpis.{kpi_name}")
        rules.append(
            KPIThresholdRule(
                kpi_name=str(kpi_name),
                enabled=bool(payload.get("enabled", True)),
                direction_preference=str(
                    payload.get("direction_preference", "informational")
                ).strip(),
                increase=_direction_threshold(
                    payload.get("increase"), f"kpis.{kpi_name}.increase"
                ),
                decrease=_direction_threshold(
                    payload.get("decrease"), f"kpis.{kpi_name}.decrease"
                ),
            )
        )
    return ThresholdManager(rules)
