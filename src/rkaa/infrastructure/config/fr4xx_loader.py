"""Load cấu hình FR-403/404/405 theo granularity của nguồn dữ liệu."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import yaml

from rkaa.domain.anomaly_detector import ChangePointConfig
from rkaa.domain.trend_analyzer import TrendAnalysisConfig


@dataclass(frozen=True, slots=True)
class FR4xxConfig:
    trend: TrendAnalysisConfig
    change_point: ChangePointConfig


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{name} phải là mapping")
    return value


def load_fr4xx_config(
    path: str | Path,
    *,
    granularity_minutes: int,
) -> FR4xxConfig:
    if granularity_minutes <= 0:
        raise ValueError("granularity_minutes phải > 0")
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = _mapping(yaml.safe_load(handle) or {}, "root")

    trend_raw = _mapping(payload.get("trend"), "trend")
    cycle_minutes = int(trend_raw.get("seasonal_cycle_minutes", 1440))
    seasonal_periods = max(2, int(round(cycle_minutes / granularity_minutes)))
    trend = TrendAnalysisConfig(
        granularity_minutes=granularity_minutes,
        analysis_window_days=int(trend_raw.get("analysis_window_days", 30)),
        minimum_clean_days=int(trend_raw.get("minimum_clean_days", 14)),
        minimum_pair_completeness=float(
            trend_raw.get("minimum_pair_completeness", 0.70)
        ),
        minimum_series_completeness=float(
            trend_raw.get("minimum_series_completeness", 0.70)
        ),
        seasonal_periods=seasonal_periods,
        r2_confident_threshold=float(trend_raw.get("r2_confident_threshold", 0.50)),
        stable_relative_slope_per_day=float(
            trend_raw.get("stable_relative_slope_per_day", 0.001)
        ),
        volatile_residual_ratio=float(trend_raw.get("volatile_residual_ratio", 0.75)),
        percent_edge_margin=float(trend_raw.get("percent_edge_margin", 25.0)),
    )

    cp_raw = _mapping(payload.get("change_point"), "change_point")
    minimum_segment_minutes = int(cp_raw.get("minimum_segment_minutes", 720))
    minimum_segment_points = max(
        2,
        int(math.ceil(minimum_segment_minutes / granularity_minutes)),
    )
    change_point = ChangePointConfig(
        penalty_scale=float(cp_raw.get("penalty_scale", 8.0)),
        minimum_segment_points=minimum_segment_points,
        detect_variance=bool(cp_raw.get("detect_variance", True)),
        search_step_points=int(cp_raw.get("search_step_points", 2)),
        localization_tolerance_periods=int(
            cp_raw.get("localization_tolerance_periods", 2)
        ),
    )
    return FR4xxConfig(trend=trend, change_point=change_point)
