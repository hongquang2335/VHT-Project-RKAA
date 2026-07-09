"""Group clean KPI samples into baseline buckets."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from rkaa.core.config import DayPeriodSettings
from rkaa.domain.day_period_classifier import classify_day_period
from rkaa.domain.week_profile_classifier import classify_week_profile


class SupportsBaselineSample(Protocol):
    """Minimal clean-sample contract required for baseline grouping."""

    ne_id: str
    kpi_name: str
    start_time: datetime
    value: float


@dataclass(frozen=True, slots=True)
class BaselineGroupKey:
    """Represents the baseline bucket dimensions for KPI samples."""

    ne_id: str
    kpi_name: str
    day_period: str
    week_profile: str


def group_baseline_samples(
    records: list[SupportsBaselineSample],
    *,
    day_periods: DayPeriodSettings | None = None,
) -> dict[BaselineGroupKey, list[float]]:
    """Group clean KPI samples by NE, KPI, day period, and week profile."""

    grouped: defaultdict[BaselineGroupKey, list[float]] = defaultdict(list)

    for record in records:
        key = BaselineGroupKey(
            ne_id=record.ne_id,
            kpi_name=record.kpi_name,
            day_period=classify_day_period(record.start_time, day_periods=day_periods).period,
            week_profile=classify_week_profile(record.start_time).profile,
        )
        grouped[key].append(record.value)

    return dict(grouped)
