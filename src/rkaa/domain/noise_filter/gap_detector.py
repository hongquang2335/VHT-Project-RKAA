"""Detect missing periods in KPI time series."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Protocol

from rkaa.core.config import ConfigError, load_settings

DEFAULT_GRANULARITY_MINUTES = 15
WARNING_GAP_THRESHOLD_HOURS = 2


class SupportsStartTime(Protocol):
    """Minimal contract required to evaluate time-series continuity."""

    start_time: datetime


@dataclass(frozen=True, slots=True)
class GapDetectionResult:
    """Represents a contiguous missing segment in a KPI time series."""

    gap_start: datetime
    gap_end: datetime
    missing_periods: int
    is_warning: bool


def detect_time_series_gaps(
    records: Iterable[SupportsStartTime],
    *,
    granularity_minutes: int | None = None,
) -> list[GapDetectionResult]:
    """Return gaps between consecutive records without interpolating values."""

    granularity = timedelta(minutes=_resolve_granularity_minutes(granularity_minutes))
    warning_threshold = timedelta(hours=WARNING_GAP_THRESHOLD_HOURS)
    ordered_records = sorted(records, key=lambda record: record.start_time)

    gaps: list[GapDetectionResult] = []
    for previous, current in zip(ordered_records, ordered_records[1:]):
        delta = current.start_time - previous.start_time
        if delta <= granularity:
            continue

        missing_periods = int(delta / granularity) - 1
        if missing_periods <= 0:
            continue

        gap_start = previous.start_time + granularity
        gap_end = gap_start + granularity * (missing_periods - 1)

        gaps.append(
            GapDetectionResult(
                gap_start=gap_start,
                gap_end=gap_end,
                missing_periods=missing_periods,
                is_warning=(gap_end - gap_start + granularity) > warning_threshold,
            )
        )

    return gaps


def _resolve_granularity_minutes(granularity_minutes: int | None) -> int:
    if granularity_minutes is not None:
        _validate_granularity_minutes(granularity_minutes)
        return granularity_minutes

    try:
        resolved = load_settings().app.granularity_minutes
    except ConfigError:
        return DEFAULT_GRANULARITY_MINUTES

    _validate_granularity_minutes(resolved)
    return resolved


def _validate_granularity_minutes(granularity_minutes: int) -> None:
    if granularity_minutes <= 0:
        raise ValueError("granularity_minutes must be a positive integer.")
