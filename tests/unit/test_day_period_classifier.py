from __future__ import annotations

from datetime import UTC, datetime

import pytest

from rkaa.core.config import DayPeriodSettings, TimeRangeSettings
from rkaa.domain.day_period_classifier import classify_day_period


def _day_periods() -> DayPeriodSettings:
    return DayPeriodSettings.model_validate(
        {
            "busy": {"start": "07:00", "end": "10:00"},
            "transition": {"start": "10:00", "end": "17:00"},
            "off_peak": {"start": "17:00", "end": "07:00"},
        }
    )


def test_classify_day_period_returns_busy() -> None:
    timestamp = datetime(2026, 7, 8, 8, 30, tzinfo=UTC)

    result = classify_day_period(timestamp, day_periods=_day_periods())

    assert result.period == "busy"


def test_classify_day_period_returns_transition() -> None:
    timestamp = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)

    result = classify_day_period(timestamp, day_periods=_day_periods())

    assert result.period == "transition"


def test_classify_day_period_handles_ranges_that_cross_midnight() -> None:
    late_night = datetime(2026, 7, 8, 23, 30, tzinfo=UTC)
    early_morning = datetime(2026, 7, 8, 5, 45, tzinfo=UTC)

    late_result = classify_day_period(late_night, day_periods=_day_periods())
    early_result = classify_day_period(early_morning, day_periods=_day_periods())

    assert late_result.period == "off_peak"
    assert early_result.period == "off_peak"


def test_classify_day_period_raises_for_ambiguous_configuration() -> None:
    timestamp = datetime(2026, 7, 8, 8, 0, tzinfo=UTC)
    overlapping_periods = DayPeriodSettings.model_validate(
        {
            "busy": {"start": "07:00", "end": "10:00"},
            "transition": {"start": "08:00", "end": "12:00"},
            "off_peak": {"start": "17:00", "end": "07:00"},
        }
    )

    with pytest.raises(ValueError, match="exactly one period"):
        classify_day_period(timestamp, day_periods=overlapping_periods)


def test_classify_day_period_raises_for_invalid_equal_start_end_range() -> None:
    timestamp = datetime(2026, 7, 8, 8, 0, tzinfo=UTC)
    invalid_periods = DayPeriodSettings(
        busy=TimeRangeSettings(start="07:00", end="10:00"),
        transition=TimeRangeSettings(start="10:00", end="17:00"),
        off_peak=TimeRangeSettings(start="17:00", end="17:00"),
    )

    with pytest.raises(ValueError, match="must not be identical"):
        classify_day_period(timestamp, day_periods=invalid_periods)
