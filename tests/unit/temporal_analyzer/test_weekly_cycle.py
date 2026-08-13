from __future__ import annotations

import pandas as pd

from rkaa.domain.temporal_analyzer import WeeklyCycleAnalyzer


def _row(timestamp: str, value: float = 99.0) -> dict[str, object]:
    return {
        "timestamp": timestamp,
        "period_end": timestamp,
        "ne_id": "NE1",
        "cell_id": "CELL_A",
        "kpi_name": "ENDC_SSR",
        "value": value,
        "unit": "%",
        "temporal_profile": "BUSY",
        "profile_timezone": "UTC",
        "minute_of_day": 8 * 60,
        "time_of_day": "08:00",
    }


def test_classify_day_maps_monday_friday_to_weekday_and_weekend() -> None:
    analyzer = WeeklyCycleAnalyzer()

    assert [analyzer.classify_day(index) for index in range(5)] == ["WEEKDAY"] * 5
    assert analyzer.classify_day(5) == "WEEKEND"
    assert analyzer.classify_day(6) == "WEEKEND"


def test_analyze_labels_weekday_weekend_and_preserves_cell() -> None:
    df = pd.DataFrame(
        [
            _row("2026-08-10T08:00:00+00:00"),  # Monday
            _row("2026-08-15T08:00:00+00:00"),  # Saturday
            _row("2026-08-16T08:00:00+00:00"),  # Sunday
        ]
    )

    result = WeeklyCycleAnalyzer().analyze(df)

    assert result.profiled_df["day_type"].tolist() == [
        "WEEKDAY",
        "WEEKEND",
        "WEEKEND",
    ]
    assert result.profiled_df["day_of_week"].tolist() == [
        "MONDAY",
        "SATURDAY",
        "SUNDAY",
    ]
    assert result.profiled_df["cell_id"].tolist() == ["CELL_A"] * 3


def test_day_type_uses_profile_timezone_not_raw_utc_calendar_day() -> None:
    row = _row("2026-08-16T23:30:00+00:00")  # Sunday UTC
    row["profile_timezone"] = "Asia/Ho_Chi_Minh"  # Monday local
    df = pd.DataFrame([row])

    result = WeeklyCycleAnalyzer().analyze(df)

    assert result.profiled_df["calendar_date"].item() == "2026-08-17"
    assert result.profiled_df["day_of_week"].item() == "MONDAY"
    assert result.profiled_df["day_type"].item() == "WEEKDAY"
