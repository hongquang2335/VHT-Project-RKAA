from __future__ import annotations

import pandas as pd

from rkaa.domain.temporal_analyzer import (
    CycleComparisonAnalyzer,
    DailyCycleComparisonConfig,
    StatisticalComparisonConfig,
    WeeklyCycleComparisonConfig,
)
from rkaa.domain.threshold_manager import (
    DirectionThreshold,
    KPIThresholdRule,
    ThresholdManager,
)


def _hourly(days: int = 16) -> pd.DataFrame:
    index = pd.date_range("2026-08-01T00:00:00Z", periods=24 * days, freq="h")
    frame = pd.DataFrame(
        {
            "timestamp": index,
            "ne_id": "NE1",
            "cell_id": "CELL1",
            "kpi_name": "KPI",
            "value": 90.0,
            "unit": "%",
        }
    )
    frame["temporal_profile"] = "BUSY"
    local = frame["timestamp"]
    frame["day_type"] = local.dt.dayofweek.map(
        lambda day: "WEEKDAY" if day <= 4 else "WEEKEND"
    )
    names = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    frame["day_of_week"] = local.dt.dayofweek.map(lambda day: names[day])
    return frame


def test_fr401_compares_latest_24h_to_historical_mean_daily_cycles() -> None:
    df = _hourly()
    # Latest 24h differs from every historical reference.
    max_ts = df["timestamp"].max()
    df.loc[df["timestamp"] > max_ts - pd.Timedelta(hours=24), "value"] = 95.0
    manager = ThresholdManager(
        [
            KPIThresholdRule(
                kpi_name="KPI",
                direction_preference="higher_is_better",
                increase=DirectionThreshold(warning=2.0, critical=4.0),
            )
        ]
    )
    analyzer = CycleComparisonAnalyzer(
        StatisticalComparisonConfig(minimum_samples_per_group=3),
        threshold_manager=manager,
    )

    result = analyzer.compare_daily_cycles(
        df,
        DailyCycleComparisonConfig(
            current_window_hours=24,
            comparison_lags_hours=(72, 144, 288),
        ),
    )

    assert set(result["reference_label"]) == {"24H_TO_72H_AVG", "24H_TO_144H_AVG", "24H_TO_288H_AVG"}
    assert (result["delta_abs"] == 5.0).all()
    assert (result["threshold_severity"] == "CRITICAL").all()
    assert result["anomaly_flag"].all()


def test_fr402_week_over_week_emits_day_type_and_day_of_week() -> None:
    df = _hourly(days=21)
    max_ts = df["timestamp"].max()
    df.loc[df["timestamp"] > max_ts - pd.Timedelta(days=7), "value"] = 92.0
    analyzer = CycleComparisonAnalyzer(StatisticalComparisonConfig())

    result = analyzer.compare_weekly_cycles(
        df,
        WeeklyCycleComparisonConfig(
            current_window_days=7,
            previous_week_enabled=True,
            previous_month_enabled=False,
        ),
    )

    assert set(result["comparison_kind"]) == {"FR402_WEEK_OVER_WEEK"}
    assert set(result["group_scope"]) == {"DAY_TYPE", "DAY_OF_WEEK"}
    assert "PREVIOUS_MONTH" not in set(result["reference_label"])
    assert (result["delta_abs"] == 2.0).all()


def test_fr402_month_comparison_exists_but_can_be_enabled_explicitly() -> None:
    df = _hourly(days=70)
    analyzer = CycleComparisonAnalyzer(StatisticalComparisonConfig())

    result = analyzer.compare_weekly_cycles(
        df,
        WeeklyCycleComparisonConfig(
            current_window_days=7,
            previous_week_enabled=False,
            previous_month_enabled=True,
            previous_month_window_days=30,
        ),
    )

    assert set(result["comparison_kind"]) == {"FR402_MONTH_OVER_MONTH"}
    assert set(result["reference_label"]) == {"PREVIOUS_MONTH"}


def test_fr303_threshold_has_priority_over_fr302_3sigma() -> None:
    df = _hourly(days=16)
    # Give the historical reference a small but non-zero variance by hour.
    df["value"] = 90.0 + df["timestamp"].dt.hour * 0.01
    max_ts = df["timestamp"].max()
    current_mask = df["timestamp"] > max_ts - pd.Timedelta(hours=24)
    df.loc[current_mask, "value"] = df.loc[current_mask, "value"] + 0.5

    manager = ThresholdManager(
        [
            KPIThresholdRule(
                kpi_name="KPI",
                direction_preference="higher_is_better",
                increase=DirectionThreshold(warning=5.0, critical=10.0),
            )
        ]
    )
    analyzer = CycleComparisonAnalyzer(
        StatisticalComparisonConfig(minimum_samples_per_group=3),
        threshold_manager=manager,
    )

    result = analyzer.compare_daily_cycles(
        df,
        DailyCycleComparisonConfig(
            current_window_hours=24,
            comparison_lags_hours=(72, 144, 288),
        ),
    )

    assert result["sigma_applicable"].all()
    assert result["anomaly_3sigma"].all()
    assert result["threshold_configured"].all()
    assert (result["threshold_severity"] == "NORMAL").all()
    assert (result["anomaly_decision_source"] == "FR303_THRESHOLD").all()
    assert not result["anomaly_flag"].any()
    assert (result["anomaly_source"] == "NONE").all()


def test_fr302_3sigma_is_fallback_when_fr303_is_not_configured() -> None:
    df = _hourly(days=16)
    df["value"] = 90.0 + df["timestamp"].dt.hour * 0.01
    max_ts = df["timestamp"].max()
    current_mask = df["timestamp"] > max_ts - pd.Timedelta(hours=24)
    df.loc[current_mask, "value"] = df.loc[current_mask, "value"] + 0.5

    analyzer = CycleComparisonAnalyzer(
        StatisticalComparisonConfig(minimum_samples_per_group=3)
    )
    result = analyzer.compare_daily_cycles(
        df,
        DailyCycleComparisonConfig(
            current_window_hours=24,
            comparison_lags_hours=(72, 144, 288),
        ),
    )

    assert result["sigma_applicable"].all()
    assert result["anomaly_3sigma"].all()
    assert not result["threshold_configured"].any()
    assert (result["anomaly_decision_source"] == "FR302_3SIGMA").all()
    assert result["anomaly_flag"].all()
    assert (result["anomaly_source"] == "FR302_3SIGMA").all()


def test_zero_variance_disables_3sigma_and_uses_fr303_if_available() -> None:
    df = _hourly(days=16)
    max_ts = df["timestamp"].max()
    df.loc[df["timestamp"] > max_ts - pd.Timedelta(hours=24), "value"] = 95.0

    no_threshold = CycleComparisonAnalyzer(
        StatisticalComparisonConfig(minimum_samples_per_group=3)
    ).compare_daily_cycles(
        df,
        DailyCycleComparisonConfig(
            current_window_hours=24,
            comparison_lags_hours=(72, 144, 288),
        ),
    )

    assert not no_threshold["sigma_applicable"].any()
    assert no_threshold["reference_z_score"].isna().all()
    assert not no_threshold["anomaly_3sigma"].any()
    assert not no_threshold["anomaly_flag"].any()
    assert (no_threshold["anomaly_decision_source"] == "FR302_3SIGMA").all()

    manager = ThresholdManager(
        [
            KPIThresholdRule(
                kpi_name="KPI",
                direction_preference="higher_is_better",
                increase=DirectionThreshold(warning=2.0, critical=4.0),
            )
        ]
    )
    with_threshold = CycleComparisonAnalyzer(
        StatisticalComparisonConfig(minimum_samples_per_group=3),
        threshold_manager=manager,
    ).compare_daily_cycles(
        df,
        DailyCycleComparisonConfig(
            current_window_hours=24,
            comparison_lags_hours=(72, 144, 288),
        ),
    )

    assert not with_threshold["sigma_applicable"].any()
    assert with_threshold["reference_z_score"].isna().all()
    assert not with_threshold["anomaly_3sigma"].any()
    assert with_threshold["anomaly_threshold"].all()
    assert with_threshold["anomaly_flag"].all()
    assert (with_threshold["anomaly_decision_source"] == "FR303_THRESHOLD").all()
    assert (with_threshold["anomaly_source"] == "FR303_THRESHOLD").all()
