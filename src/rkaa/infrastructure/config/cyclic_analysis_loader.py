"""Load FR-401/402 periodic comparison configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from rkaa.domain.temporal_analyzer.cycle_comparison import (
    DailyCycleComparisonConfig,
    StatisticalComparisonConfig,
    WeeklyCycleComparisonConfig,
)


@dataclass(frozen=True, slots=True)
class CyclicAnalysisConfig:
    statistical: StatisticalComparisonConfig
    fr401: DailyCycleComparisonConfig
    fr402: WeeklyCycleComparisonConfig


def _mapping(value: Any, context: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{context} phải là mapping")
    return value


def load_cyclic_analysis_config(path: str | Path) -> CyclicAnalysisConfig:
    with Path(path).open("r", encoding="utf-8") as handle:
        root = _mapping(yaml.safe_load(handle) or {}, "root")

    statistical_raw = _mapping(root.get("statistical"), "statistical")
    statistical = StatisticalComparisonConfig(
        alpha=float(statistical_raw.get("alpha", 0.05)),
        sigma_threshold=float(statistical_raw.get("sigma_threshold", 3.0)),
        minimum_samples_per_group=int(
            statistical_raw.get("minimum_samples_per_group", 3)
        ),
    )

    fr401_raw = _mapping(root.get("fr401"), "fr401")
    raw_lags = fr401_raw.get("comparison_lags_hours", [72, 144, 288])
    if not isinstance(raw_lags, list):
        raise ValueError("fr401.comparison_lags_hours phải là list")
    fr401 = DailyCycleComparisonConfig(
        current_window_hours=int(fr401_raw.get("current_window_hours", 24)),
        comparison_lags_hours=tuple(int(value) for value in raw_lags),
    )

    fr402_raw = _mapping(root.get("fr402"), "fr402")
    previous_week = _mapping(fr402_raw.get("previous_week"), "fr402.previous_week")
    previous_month = _mapping(fr402_raw.get("previous_month"), "fr402.previous_month")
    fr402 = WeeklyCycleComparisonConfig(
        current_window_days=int(fr402_raw.get("current_window_days", 7)),
        previous_week_enabled=bool(previous_week.get("enabled", True)),
        previous_month_enabled=bool(previous_month.get("enabled", False)),
        previous_month_window_days=int(previous_month.get("window_days", 30)),
    )
    return CyclicAnalysisConfig(statistical=statistical, fr401=fr401, fr402=fr402)
