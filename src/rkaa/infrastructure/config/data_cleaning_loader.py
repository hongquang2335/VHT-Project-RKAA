"""Đọc cấu hình FR-201 từ YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from rkaa.domain.noise_filter.models import (
    CustomRuleConfig,
    IQRConfig,
    ImpactWindowConfig,
    NoiseFilterConfig,
    NullSentinelConfig,
    RangeRule,
    RestartConfig,
    StatisticalOutlierConfig,
    ZScoreConfig,
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


def _float(mapping: dict[str, Any], key: str, default: float) -> float:
    value = mapping.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} phải là số")
    return float(value)


def _int(mapping: dict[str, Any], key: str, default: int) -> int:
    value = mapping.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} phải là số nguyên")
    return value


def _str(mapping: dict[str, Any], key: str, default: str) -> str:
    value = mapping.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"{key} phải là chuỗi")
    return value


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} phải là danh sách chuỗi")
    return tuple(item.strip() for item in value if item.strip())


def _number_tuple(value: Any, field_name: str) -> tuple[float, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{field_name} phải là danh sách số")
    result: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{field_name} phải chỉ chứa số")
        result.append(float(item))
    return tuple(result)


def load_data_cleaning_config(path: str | Path) -> NoiseFilterConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    root = _mapping(payload, "root")
    filters = _mapping(root.get("filters"), "filters")

    null_raw = _mapping(filters.get("null_sentinel"), "filters.null_sentinel")
    per_kpi_raw = _mapping(null_raw.get("per_kpi"), "filters.null_sentinel.per_kpi")
    per_kpi = {
        str(kpi_name): _number_tuple(values, f"null_sentinel.per_kpi.{kpi_name}")
        for kpi_name, values in per_kpi_raw.items()
    }
    null_config = NullSentinelConfig(
        enabled=_bool(null_raw, "enabled", True),
        global_values=_number_tuple(null_raw.get("global_values"), "global_values"),
        per_kpi=per_kpi,
    )

    impact_raw = _mapping(filters.get("impact_window"), "filters.impact_window")
    impact_config = ImpactWindowConfig(
        enabled=_bool(impact_raw, "enabled", True),
        excluded_impact_types=_string_tuple(
            impact_raw.get("excluded_impact_types"),
            "impact_window.excluded_impact_types",
        ),
        match_mode=_str(impact_raw, "match_mode", "exact_or_prefix"),
    )
    if impact_config.match_mode not in {"exact", "exact_or_prefix"}:
        raise ValueError("impact_window.match_mode chỉ nhận exact hoặc exact_or_prefix")

    restart_raw = _mapping(filters.get("restart"), "filters.restart")
    restart_config = RestartConfig(
        enabled=_bool(restart_raw, "enabled", False),
        eligible_metrics=_string_tuple(
            restart_raw.get("eligible_metrics"),
            "restart.eligible_metrics",
        ),
        reset_max_value=_float(restart_raw, "reset_max_value", 100.0),
        min_previous_value=_float(restart_raw, "min_previous_value", 1000.0),
        min_drop_ratio=_float(restart_raw, "min_drop_ratio", 0.90),
        confirmation_points=_int(restart_raw, "confirmation_points", 2),
        concurrent_window_minutes=_int(restart_raw, "concurrent_window_minutes", 15),
        min_concurrent_counters=_int(restart_raw, "min_concurrent_counters", 2),
        post_restart_grace_minutes=_int(restart_raw, "post_restart_grace_minutes", 15),
    )
    if not 0 <= restart_config.min_drop_ratio <= 1:
        raise ValueError("restart.min_drop_ratio phải nằm trong [0, 1]")
    if restart_config.confirmation_points < 0:
        raise ValueError("restart.confirmation_points phải >= 0")
    if restart_config.min_concurrent_counters < 1:
        raise ValueError("restart.min_concurrent_counters phải >= 1")

    statistical_raw = _mapping(
        filters.get("statistical_outlier"),
        "filters.statistical_outlier",
    )
    iqr_raw = _mapping(statistical_raw.get("iqr"), "statistical_outlier.iqr")
    z_raw = _mapping(statistical_raw.get("z_score"), "statistical_outlier.z_score")

    iqr_config = IQRConfig(
        enabled=_bool(iqr_raw, "enabled", True),
        multiplier=_float(iqr_raw, "multiplier", 1.5),
        min_samples=_int(iqr_raw, "min_samples", 24),
        insufficient_samples=_str(iqr_raw, "insufficient_samples", "skip"),
        zero_iqr=_str(iqr_raw, "zero_iqr", "skip"),
    )
    z_config = ZScoreConfig(
        enabled=_bool(z_raw, "enabled", False),
        threshold=_float(z_raw, "threshold", 3.0),
        min_samples=_int(z_raw, "min_samples", 100),
        insufficient_samples=_str(z_raw, "insufficient_samples", "skip"),
        zero_std=_str(z_raw, "zero_std", "skip"),
    )
    if iqr_config.min_samples < 1 or z_config.min_samples < 1:
        raise ValueError("min_samples phải >= 1")
    if iqr_config.insufficient_samples != "skip" or z_config.insufficient_samples != "skip":
        raise ValueError("Hiện FR-201 chỉ hỗ trợ insufficient_samples=skip")
    if iqr_config.zero_iqr != "skip" or z_config.zero_std != "skip":
        raise ValueError("Hiện FR-201 chỉ hỗ trợ zero_iqr/zero_std=skip")

    statistical_config = StatisticalOutlierConfig(
        enabled=_bool(statistical_raw, "enabled", True),
        combination=_str(statistical_raw, "combination", "any"),
        iqr=iqr_config,
        z_score=z_config,
    )
    if statistical_config.combination not in {"any", "all"}:
        raise ValueError("statistical_outlier.combination chỉ nhận any hoặc all")

    custom_raw = _mapping(filters.get("custom_rule"), "filters.custom_rule")
    rules_raw = _mapping(custom_raw.get("rules"), "custom_rule.rules")
    rules: dict[str, RangeRule] = {}
    for kpi_name, raw_rule in rules_raw.items():
        rule_mapping = _mapping(raw_rule, f"custom_rule.rules.{kpi_name}")
        min_value = rule_mapping.get("min")
        max_value = rule_mapping.get("max")
        if min_value is not None:
            if isinstance(min_value, bool) or not isinstance(min_value, (int, float)):
                raise ValueError(f"custom rule min của {kpi_name} phải là số")
            min_value = float(min_value)
        if max_value is not None:
            if isinstance(max_value, bool) or not isinstance(max_value, (int, float)):
                raise ValueError(f"custom rule max của {kpi_name} phải là số")
            max_value = float(max_value)
        if min_value is not None and max_value is not None and min_value > max_value:
            raise ValueError(f"custom rule của {kpi_name}: min > max")
        rules[str(kpi_name)] = RangeRule(min_value=min_value, max_value=max_value)

    custom_config = CustomRuleConfig(
        enabled=_bool(custom_raw, "enabled", True),
        rules=rules,
    )

    return NoiseFilterConfig(
        null_sentinel=null_config,
        impact_window=impact_config,
        restart=restart_config,
        statistical_outlier=statistical_config,
        custom_rule=custom_config,
    )
