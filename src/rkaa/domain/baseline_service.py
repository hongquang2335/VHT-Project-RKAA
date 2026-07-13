"""Service for computing and storing KPI baselines from clean records."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from rkaa.core.config import DayPeriodSettings
from rkaa.domain.baseline_confidence import assess_baseline_confidence
from rkaa.domain.baseline_grouping import BaselineGroupKey
from rkaa.domain.baseline_statistics import compute_baseline_statistics
from rkaa.domain.day_period_classifier import classify_day_period
from rkaa.domain.week_profile_classifier import classify_week_profile
from rkaa.infrastructure.data_store.models.baseline import Baseline
from rkaa.infrastructure.data_store.repositories.baseline import BaselineRepository


class SupportsBaselineRecord(Protocol):
    """Minimal clean-record contract required for baseline service orchestration."""

    ne_id: str
    kpi_name: str
    start_time: datetime
    value: float


@dataclass(frozen=True, slots=True)
class BaselineComputationResult:
    """Represents the persisted baselines produced by one compute run."""

    baselines: list[Baseline]


def compute_and_store_baselines(
    records: list[SupportsBaselineRecord],
    *,
    repository: BaselineRepository,
    day_periods: DayPeriodSettings | None = None,
    required_clean_days: int | None = None,
    computed_at: datetime | None = None,
) -> BaselineComputationResult:
    """Compute grouped baseline summaries from clean records and persist them."""

    if not records:
        return BaselineComputationResult(baselines=[])

    grouped_records = _group_records_by_key(records, day_periods=day_periods)
    persisted: list[Baseline] = []
    resolved_computed_at = computed_at or datetime.now(UTC)

    for key in sorted(grouped_records, key=_group_sort_key):
        grouped = grouped_records[key]
        statistics = compute_baseline_statistics(record.value for record in grouped)
        confidence = assess_baseline_confidence(
            grouped,
            required_clean_days=required_clean_days,
        )
        persisted.append(
            repository.upsert(
                Baseline(
                    ne_id=key.ne_id,
                    kpi_name=key.kpi_name,
                    day_period=key.day_period,
                    week_profile=key.week_profile,
                    mean_value=statistics.mean,
                    median_value=statistics.median,
                    std_value=statistics.std,
                    p5_value=statistics.p5,
                    p95_value=statistics.p95,
                    sample_count=statistics.sample_count,
                    clean_day_count=confidence.clean_day_count,
                    required_day_count=confidence.required_day_count,
                    confidence_status=confidence.status,
                    computed_at=resolved_computed_at,
                )
            )
        )

    return BaselineComputationResult(baselines=persisted)


def _group_records_by_key(
    records: list[SupportsBaselineRecord],
    *,
    day_periods: DayPeriodSettings | None = None,
) -> dict[BaselineGroupKey, list[SupportsBaselineRecord]]:
    grouped: defaultdict[BaselineGroupKey, list[SupportsBaselineRecord]] = defaultdict(list)

    for record in records:
        key = BaselineGroupKey(
            ne_id=record.ne_id,
            kpi_name=record.kpi_name,
            day_period=classify_day_period(record.start_time, day_periods=day_periods).period,
            week_profile=classify_week_profile(record.start_time).profile,
        )
        grouped[key].append(record)

    return dict(grouped)


def _group_sort_key(key: BaselineGroupKey) -> tuple[str, str, str, str]:
    return (key.ne_id, key.kpi_name, key.week_profile, key.day_period)
