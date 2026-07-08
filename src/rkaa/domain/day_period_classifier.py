"""Classify timestamps into configured day periods."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

from rkaa.core.config import DayPeriodSettings, TimeRangeSettings, load_settings


@dataclass(frozen=True, slots=True)
class DayPeriodClassification:
    """Represents the classified day-period bucket for a timestamp."""

    period: str


def classify_day_period(
    timestamp: datetime,
    *,
    day_periods: DayPeriodSettings | None = None,
) -> DayPeriodClassification:
    """Classify a timestamp as busy, off_peak, or transition."""

    configured_periods = day_periods or load_settings().app.day_periods
    current_time = timestamp.timetz().replace(tzinfo=None)

    matches = [
        period_name
        for period_name, time_range in (
            ("busy", configured_periods.busy),
            ("off_peak", configured_periods.off_peak),
            ("transition", configured_periods.transition),
        )
        if _is_within_time_range(current_time, time_range)
    ]

    if len(matches) != 1:
        raise ValueError("Configured day periods must map each timestamp to exactly one period.")

    return DayPeriodClassification(period=matches[0])


def _is_within_time_range(current_time: time, time_range: TimeRangeSettings) -> bool:
    start = time_range.start
    end = time_range.end

    if start < end:
        return start <= current_time < end

    if start > end:
        return current_time >= start or current_time < end

    raise ValueError("Day period start and end times must not be identical.")
