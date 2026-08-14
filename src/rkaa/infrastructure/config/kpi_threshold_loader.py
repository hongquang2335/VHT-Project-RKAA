"""Đọc cấu hình threshold KPI từ YAML cho FR-303."""

from __future__ import annotations

from pathlib import Path

import yaml

from rkaa.domain.threshold_manager import (
    DirectionPreference,
    DirectionThresholds,
    KpiThresholdPolicy,
    ThresholdLevel,
    ThresholdMode,
    ThresholdManagerService,
)


def _parse_level(raw: object, *, label: str) -> ThresholdLevel | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"{label} phải là đối tượng gồm type và value")

    raw_mode = str(raw.get("type", "")).strip().upper()
    try:
        mode = ThresholdMode(raw_mode)
    except ValueError as exc:
        raise ValueError(f"{label}.type không hợp lệ: {raw_mode!r}") from exc

    try:
        value = float(raw["value"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{label}.value phải là số") from exc
    return ThresholdLevel(mode=mode, value=value)


def _parse_direction(raw: object, *, label: str) -> DirectionThresholds:
    if raw is None:
        return DirectionThresholds()
    if not isinstance(raw, dict):
        raise ValueError(f"{label} phải là đối tượng")

    warning = _parse_level(raw.get("warning"), label=f"{label}.warning")
    critical = _parse_level(raw.get("critical"), label=f"{label}.critical")
    if (
        warning is not None
        and critical is not None
        and warning.mode is critical.mode
        and critical.value < warning.value
    ):
        raise ValueError(
            f"{label}: critical phải >= warning khi dùng cùng kiểu threshold"
        )
    return DirectionThresholds(warning=warning, critical=critical)


def load_kpi_threshold_policies(path: str | Path) -> dict[str, KpiThresholdPolicy]:
    """Đọc và validate toàn bộ policy threshold theo KPI."""

    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    raw_kpis = raw.get("kpis", {})
    if not isinstance(raw_kpis, dict):
        raise ValueError("kpis trong threshold config phải là đối tượng")

    policies: dict[str, KpiThresholdPolicy] = {}
    for raw_name, raw_policy in raw_kpis.items():
        kpi_name = str(raw_name).strip()
        if not kpi_name:
            raise ValueError("Tên KPI trong threshold config không được rỗng")
        if raw_policy is None:
            raw_policy = {}
        if not isinstance(raw_policy, dict):
            raise ValueError(f"Cấu hình KPI {kpi_name} phải là đối tượng")

        raw_preference = str(
            raw_policy.get("direction_preference", DirectionPreference.INFORMATIONAL.value)
        ).strip().lower()
        try:
            preference = DirectionPreference(raw_preference)
        except ValueError as exc:
            raise ValueError(
                f"direction_preference của {kpi_name} không hợp lệ: {raw_preference!r}"
            ) from exc

        policies[kpi_name] = KpiThresholdPolicy(
            kpi_name=kpi_name,
            direction_preference=preference,
            increase=_parse_direction(
                raw_policy.get("increase"),
                label=f"{kpi_name}.increase",
            ),
            decrease=_parse_direction(
                raw_policy.get("decrease"),
                label=f"{kpi_name}.decrease",
            ),
        )
    return policies


def load_threshold_manager(path: str | Path) -> ThresholdManagerService:
    """Tạo threshold manager từ file YAML."""

    return ThresholdManagerService(load_kpi_threshold_policies(path))
