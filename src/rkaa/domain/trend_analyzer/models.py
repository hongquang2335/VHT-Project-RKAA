"""Domain models cho FR-403/FR-404 và eligibility theo NE + Cell."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class TrendAnalysisConfig:
    granularity_minutes: int = 60
    minimum_clean_days: int = 14
    minimum_pair_completeness: float = 0.70
    minimum_series_completeness: float = 0.70
    seasonal_periods: int = 24
    r2_confident_threshold: float = 0.50
    stable_relative_slope_per_day: float = 0.001
    volatile_residual_ratio: float = 0.75
    percent_edge_margin: float = 25.0


@dataclass(slots=True)
class TrendAnalysisResult:
    pair_validity_df: pd.DataFrame
    trend_df: pd.DataFrame
    components_df: pd.DataFrame
