from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from rkaa.application.impact_analyzer import ImpactAnalysisConfig, ImpactAnalyzer
from rkaa.domain.baseline_engine import BaselineEngine
from rkaa.domain.impact_manager.models import (
    EventCategory,
    ImpactEvent,
    ImpactSource,
    ImpactStatus,
)
from rkaa.domain.temporal_analyzer.models import (
    ProfileWindow,
    TemporalProfile,
    TemporalProfileConfig,
)
from rkaa.domain.temporal_analyzer.service import TemporalAnalyzer


def _temporal() -> TemporalAnalyzer:
    return TemporalAnalyzer(
        TemporalProfileConfig(
            timezone="UTC",
            windows=(
                ProfileWindow(TemporalProfile.BUSY, 7 * 60, 21 * 60),
                ProfileWindow(TemporalProfile.TRANSITION, 6 * 60, 7 * 60),
                ProfileWindow(TemporalProfile.TRANSITION, 21 * 60, 22 * 60),
                ProfileWindow(TemporalProfile.OFF_PEAK, 22 * 60, 6 * 60),
            ),
        )
    )


def _impact() -> ImpactEvent:
    now = datetime(2026, 1, 22, tzinfo=timezone.utc)
    return ImpactEvent(
        impact_id="impact-1",
        ne_id="NE1",
        cell_id="CELL1",
        t1_utc=now,
        t2_utc=now,
        impact_type="TEST",
        description="test",
        operator="tester",
        source=ImpactSource.MANUAL,
        status=ImpactStatus.CLOSED,
        created_at_utc=now,
        updated_at_utc=now,
        event_category=EventCategory.IMPACT,
    )


def _frame() -> pd.DataFrame:
    timestamps = pd.date_range("2026-01-01T00:00:00Z", "2026-01-23T23:00:00Z", freq="h")
    rows = []
    impact_start = pd.Timestamp("2026-01-22T00:00:00Z")
    for ts in timestamps:
        # Historical same-weekday/same-hour baseline is non-constant across weeks.
        day_offset = (ts.normalize() - pd.Timestamp("2026-01-01T00:00:00Z")).days
        value = 100.0 + day_offset * 0.15 + ts.hour * 0.01
        if impact_start <= ts < impact_start + pd.Timedelta(hours=24):
            value += 15.0
        rows.append(
            {
                "timestamp": ts,
                "period_end": ts + pd.Timedelta(hours=1),
                "ne_id": "NE1",
                "cell_id": "CELL1",
                "kpi_name": "KPI_A",
                "value": value,
                "unit": "%",
            }
        )
    return pd.DataFrame(rows)


class SpyBaselineEngine(BaselineEngine):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def compare_same_day_type_windows(self, pre_df: pd.DataFrame, post_df: pd.DataFrame) -> pd.DataFrame:
        self.calls.append("compare_same_day_type_windows")
        return super().compare_same_day_type_windows(pre_df, post_df)

    def select_corresponding_history(self, history_df: pd.DataFrame, target_df: pd.DataFrame) -> pd.DataFrame:
        self.calls.append("select_corresponding_history")
        return super().select_corresponding_history(history_df, target_df)

    def compute(self, profiled_df: pd.DataFrame) -> pd.DataFrame:
        self.calls.append("compute")
        return super().compute(profiled_df)

    def annotate_reliability(self, profiled_df: pd.DataFrame, baseline_df: pd.DataFrame, *, minimum_clean_days: int = 14) -> pd.DataFrame:
        self.calls.append("annotate_reliability")
        return super().annotate_reliability(
            profiled_df,
            baseline_df,
            minimum_clean_days=minimum_clean_days,
        )


def test_fr301_fr302_reuses_existing_temporal_and_baseline_cores() -> None:
    baseline = SpyBaselineEngine()
    analyzer = ImpactAnalyzer(
        temporal_analyzer=_temporal(),
        baseline_engine=baseline,
        config=ImpactAnalysisConfig(window_hours=24),
    )

    result = analyzer.analyze(
        _frame(),
        _impact(),
        direction_preferences={"KPI_A": "higher_is_better"},
    )

    assert not result.empty
    assert set(result["impact_type"]) == {"TEST"}
    assert {
        "compare_same_day_type_windows",
        "select_corresponding_history",
        "compute",
        "annotate_reliability",
    }.issubset(set(baseline.calls))
    assert result["comparison_eligible"].all()
    assert result["baseline_reliable"].all()
    assert result["statistically_significant"].any()
    assert (result["change_assessment"] == "IMPROVED").any()
    assert result["anomaly_3sigma"].any()
    assert result["anomaly_flag"].any()
    assert set(result["baseline_reference"]) == {"SAME_WEEKDAY_SAME_MINUTE_OF_DAY"}


def test_baseline_selector_matches_same_weekday_and_minute_only() -> None:
    temporal = _temporal()
    profiled = temporal.analyze(_frame()).profiled_df
    from rkaa.domain.temporal_analyzer.weekly_cycle import WeeklyCycleAnalyzer

    profiled = WeeklyCycleAnalyzer().analyze(profiled).profiled_df
    target = profiled[
        (profiled["timestamp"] >= pd.Timestamp("2026-01-22T07:00:00Z"))
        & (profiled["timestamp"] < pd.Timestamp("2026-01-22T08:00:00Z"))
    ]
    history = profiled[profiled["timestamp"] < pd.Timestamp("2026-01-21T00:00:00Z")]
    matched = BaselineEngine().select_corresponding_history(history, target)

    assert not matched.empty
    assert set(matched["day_of_week"]) == {"THURSDAY"}
    assert set(matched["minute_of_day"]) == {7 * 60}
    assert set(matched["temporal_profile"]) == {"BUSY"}
