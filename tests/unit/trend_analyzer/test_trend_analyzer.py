from __future__ import annotations

import numpy as np
import pandas as pd

from rkaa.domain.trend_analyzer import TrendAnalysisConfig, TrendAnalyzer


def _series(
    *,
    kpi: str,
    unit: str,
    slope_per_day: float,
    base: float,
    periods: int = 24 * 20,
) -> pd.DataFrame:
    timestamps = pd.date_range("2026-01-01", periods=periods, freq="h", tz="UTC")
    x_days = np.arange(periods) / 24.0
    seasonal = 0.2 * np.sin(2 * np.pi * np.arange(periods) / 24.0)
    values = base + slope_per_day * x_days + seasonal
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "ne_id": "NE1",
            "cell_id": "CELL1",
            "kpi_name": kpi,
            "value": values,
            "unit": unit,
        }
    )


def _config() -> TrendAnalysisConfig:
    return TrendAnalysisConfig(
        granularity_minutes=60,
        minimum_clean_days=14,
        seasonal_periods=24,
        r2_confident_threshold=0.5,
        stable_relative_slope_per_day=0.0001,
        volatile_residual_ratio=0.95,
    )


def test_fr403_higher_is_better_positive_slope_is_improving() -> None:
    result = TrendAnalyzer(_config()).analyze(
        _series(kpi="SSR", unit="%", slope_per_day=0.05, base=95.0),
        direction_preferences={"SSR": "higher_is_better"},
    )
    row = result.trend_df.iloc[0]
    assert bool(row["series_eligible"]) is True
    assert bool(row["confident"]) is True
    assert row["trend_label"] == "improving"
    assert row["trend_slope_per_day"] > 0
    assert len(result.components_df) == 24 * 20


def test_fr404_infers_percent_direction_only_near_an_edge() -> None:
    analyzer = TrendAnalyzer(_config())
    pref_high, confidence_high, edge_high, distance_high = analyzer.infer_percent_direction(
        pd.Series([95.0, 96.0, 97.0]), edge_margin=25.0
    )
    pref_low, confidence_low, edge_low, distance_low = analyzer.infer_percent_direction(
        pd.Series([3.0, 4.0, 5.0]), edge_margin=25.0
    )
    pref_mid, confidence, edge_mid, distance_mid = analyzer.infer_percent_direction(
        pd.Series([45.0, 50.0, 55.0]), edge_margin=25.0
    )
    assert pref_high == "higher_is_better"
    assert edge_high == "100"
    assert confidence_high > 0
    assert distance_high < 10
    assert pref_low == "lower_is_better"
    assert edge_low == "0"
    assert confidence_low > 0
    assert distance_low < 10
    assert pref_mid == "informational"
    assert edge_mid == "MIDDLE"
    assert distance_mid >= 45
    assert confidence == 0.0


def test_fr404_outputs_auditable_percent_statistics_and_uses_auto_semantic_when_unconfigured() -> None:
    result = TrendAnalyzer(_config()).analyze(
        _series(kpi="AUTO_PERCENT", unit="%", slope_per_day=0.05, base=95.0),
        direction_preferences={"AUTO_PERCENT": "informational"},
    )
    row = result.trend_df.iloc[0]
    assert bool(row["fr404_applicable"]) is True
    assert row["fr404_nearest_edge"] == "100"
    assert row["fr404_inferred_direction"] == "higher_is_better"
    assert row["direction_preference_source"] == "fr404_percent_statistics"
    assert row["direction_preference"] == "higher_is_better"


def test_fr404_configured_semantic_has_priority_but_auto_inference_is_still_reported() -> None:
    result = TrendAnalyzer(_config()).analyze(
        _series(kpi="CONFIGURED", unit="%", slope_per_day=0.05, base=95.0),
        direction_preferences={"CONFIGURED": "lower_is_better"},
    )
    row = result.trend_df.iloc[0]
    assert row["fr404_inferred_direction"] == "higher_is_better"
    assert row["configured_direction_preference"] == "lower_is_better"
    assert row["direction_preference"] == "lower_is_better"
    assert row["direction_preference_source"] == "configured"
    assert row["trend_label"] == "degrading"


def test_fr403_fr404_limit_analysis_to_latest_configured_window() -> None:
    config = TrendAnalysisConfig(
        granularity_minutes=60,
        analysis_window_days=30,
        minimum_clean_days=14,
        seasonal_periods=24,
        r2_confident_threshold=0.5,
        stable_relative_slope_per_day=0.0001,
        volatile_residual_ratio=0.95,
    )
    frame = _series(
        kpi="WINDOWED",
        unit="%",
        slope_per_day=0.02,
        base=90.0,
        periods=24 * 45,
    )
    result = TrendAnalyzer(config).analyze(
        frame,
        direction_preferences={"WINDOWED": "higher_is_better"},
    )
    row = result.trend_df.iloc[0]
    assert row["analysis_window_days"] == 30
    assert int(row["expected_points"]) <= 30 * 24 + 1
    assert int(row["expected_points"]) >= 29 * 24
