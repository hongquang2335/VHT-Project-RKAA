"""Đọc cấu hình FR-203 từ YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from rkaa.domain.data_quality.models import (
    DataQualityConfig,
    DuplicateConfig,
    GapConfig,
    LocalSpikeConfig,
    NormalizationConfig,
    QualityRangeRule,
    RangeValidationConfig,
)


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} phải là mapping/object trong YAML")
    return value


def _bool(mapping: dict[str, Any], key: str, default: bool) -> bool:
    value = mapping.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} phải là true/false")
    return value


def _int(mapping: dict[str, Any], key: str, default: int) -> int:
    value = mapping.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} phải là số nguyên")
    return value


def _float(mapping: dict[str, Any], key: str, default: float) -> float:
    value = mapping.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} phải là số")
    return float(value)


def _str(mapping: dict[str, Any], key: str, default: str) -> str:
    value = mapping.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"{key} phải là chuỗi")
    return value


def _resolve_related_path(config_path: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    # data_quality.yaml nằm trong <root>/configs => parent.parent là project root.
    return config_path.parent.parent / path


def _read_nested_mapping(payload: dict[str, Any], dotted_path: str) -> dict[str, Any]:
    current: Any = payload
    for part in dotted_path.split("."):
        current = _mapping(current, dotted_path).get(part)
    return _mapping(current, dotted_path)


def _load_range_rules(
    *,
    config_path: Path,
    range_raw: dict[str, Any],
) -> dict[str, QualityRangeRule]:
    rules_file = _str(range_raw, "rules_file", "configs/data_cleaning.yaml")
    rules_path = _str(range_raw, "rules_path", "filters.custom_rule.rules")
    source_path = _resolve_related_path(config_path, rules_file)
    if not source_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file rule KPI: {source_path}")

    with source_path.open("r", encoding="utf-8") as handle:
        source_payload = yaml.safe_load(handle) or {}
    rules_raw = _read_nested_mapping(_mapping(source_payload, "rules root"), rules_path)

    result: dict[str, QualityRangeRule] = {}
    for kpi_name, raw in rules_raw.items():
        rule = _mapping(raw, f"range rule {kpi_name}")
        min_value = rule.get("min")
        max_value = rule.get("max")
        if min_value is not None:
            if isinstance(min_value, bool) or not isinstance(min_value, (int, float)):
                raise ValueError(f"min của {kpi_name} phải là số")
            min_value = float(min_value)
        if max_value is not None:
            if isinstance(max_value, bool) or not isinstance(max_value, (int, float)):
                raise ValueError(f"max của {kpi_name} phải là số")
            max_value = float(max_value)
        result[str(kpi_name)] = QualityRangeRule(
            min_value=min_value,
            max_value=max_value,
        )
    return result


def load_data_quality_config(path: str | Path) -> DataQualityConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        payload = _mapping(yaml.safe_load(handle) or {}, "root")

    normalization_raw = _mapping(payload.get("normalization"), "normalization")
    duplicate_raw = _mapping(
        payload.get("duplicate_detection"),
        "duplicate_detection",
    )
    gap_raw = _mapping(payload.get("gap_detection"), "gap_detection")
    range_raw = _mapping(payload.get("range_validation"), "range_validation")
    spike_raw = _mapping(payload.get("local_spike"), "local_spike")

    normalization = NormalizationConfig(
        enabled=_bool(normalization_raw, "enabled", True),
        assume_naive_timezone=_str(
            normalization_raw,
            "assume_naive_timezone",
            "UTC",
        ),
    )
    if not normalization.enabled:
        raise ValueError(
            "FR-203 cần normalization.enabled=true vì gap/duplicate/range đều dùng "
            "timestamp và value đã chuẩn hóa"
        )
    if normalization.assume_naive_timezone.upper() != "UTC":
        raise ValueError(
            "Bản FR-203 hiện tại chỉ hỗ trợ assume_naive_timezone=UTC "
            "để khớp quy ước collection/FR-201 hiện có"
        )

    duplicate = DuplicateConfig(enabled=_bool(duplicate_raw, "enabled", True))
    gap = GapConfig(
        enabled=_bool(gap_raw, "enabled", True),
        expected_interval_minutes=_int(gap_raw, "expected_interval_minutes", 15),
        warning_threshold_minutes=_int(gap_raw, "warning_threshold_minutes", 120),
    )
    if gap.expected_interval_minutes < 1:
        raise ValueError("expected_interval_minutes phải >= 1")
    if gap.warning_threshold_minutes < gap.expected_interval_minutes:
        raise ValueError("warning_threshold_minutes phải >= expected_interval_minutes")

    range_enabled = _bool(range_raw, "enabled", True)
    counter_min_value = range_raw.get("counter_min_value", 0.0)
    if counter_min_value is not None:
        if isinstance(counter_min_value, bool) or not isinstance(
            counter_min_value, (int, float)
        ):
            raise ValueError("range_validation.counter_min_value phải là số hoặc null")
        counter_min_value = float(counter_min_value)

    range_validation = RangeValidationConfig(
        enabled=range_enabled,
        rules=(
            _load_range_rules(config_path=config_path, range_raw=range_raw)
            if range_enabled
            else {}
        ),
        counter_min_value=counter_min_value,
    )
    local_spike = LocalSpikeConfig(
        enabled=_bool(spike_raw, "enabled", True),
        window_samples=_int(spike_raw, "window_samples", 96),
        min_samples=_int(spike_raw, "min_samples", 24),
        robust_z_threshold=_float(spike_raw, "robust_z_threshold", 6.0),
    )
    if local_spike.min_samples < 1:
        raise ValueError("local_spike.min_samples phải >= 1")
    if local_spike.window_samples < local_spike.min_samples:
        raise ValueError("local_spike.window_samples phải >= min_samples")
    if local_spike.robust_z_threshold <= 0:
        raise ValueError("local_spike.robust_z_threshold phải > 0")

    return DataQualityConfig(
        normalization=normalization,
        duplicate=duplicate,
        gap=gap,
        range_validation=range_validation,
        local_spike=local_spike,
    )
