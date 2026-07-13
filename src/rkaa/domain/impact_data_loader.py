"""Load clean pre/post KPI samples for one impact analysis run."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from rkaa.core.config import DayPeriodSettings, load_settings
from rkaa.domain.day_period_classifier import classify_day_period
from rkaa.domain.week_profile_classifier import classify_week_profile
from rkaa.domain.window_resolver import TimeWindow, resolve_impact_windows

MINIMUM_COMPLETENESS = 0.7


class SupportsImpactEvent(Protocol):
    """Minimal impact-event contract required for loading analysis samples."""

    ne_id: str
    t1: datetime
    t2: datetime | None


class SupportsKPIRecord(Protocol):
    """Minimal KPI record contract required for impact data loading."""

    ne_id: str
    kpi_name: str
    start_time: datetime
    end_time: datetime
    value: float
    quality_flag: str | None
    is_noise: bool


class SupportsKPIRecordRepository(Protocol):
    """Repository contract required for time-range lookups."""

    def find_by_ne_kpi_time_range(
        self,
        *,
        ne_id: str,
        kpi_name: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[SupportsKPIRecord]: ...


@dataclass(frozen=True, slots=True)
class ImpactSampleWindow:
    """Prepared clean KPI samples for one comparison window."""

    records: list[SupportsKPIRecord]
    expected_count: int
    clean_count: int
    completeness: float
    status: str
    time_window: TimeWindow


@dataclass(frozen=True, slots=True)
class ImpactDataLoadResult:
    """Pre/post datasets prepared for downstream impact analysis."""

    ne_id: str
    kpi_name: str
    day_period: str
    week_profile: str
    pre_window: ImpactSampleWindow
    post_window: ImpactSampleWindow


def load_impact_kpi_samples(
    *,
    impact_event: SupportsImpactEvent,
    kpi_name: str,
    repository: SupportsKPIRecordRepository,
    pre_window_hours: int,
    recovery_buffer_hours: int,
    post_window_hours: int = 2,
    granularity_minutes: int | None = None,
    day_periods: DayPeriodSettings | None = None,
) -> ImpactDataLoadResult:
    """Load clean pre/post KPI samples aligned to the impact comparison bucket."""

    windows = resolve_impact_windows(
        t1=impact_event.t1,
        t2=impact_event.t2,
        pre_window_hours=pre_window_hours,
        post_window_hours=post_window_hours,
        recovery_buffer_hours=recovery_buffer_hours,
    )
    resolved_day_periods = day_periods or load_settings().app.day_periods
    resolved_granularity_minutes = granularity_minutes or load_settings().app.granularity_minutes

    impact_day_period = classify_day_period(
        _normalize_timestamp(impact_event.t1),
        day_periods=resolved_day_periods,
    ).period
    impact_week_profile = classify_week_profile(_normalize_timestamp(impact_event.t1)).profile

    pre_records = repository.find_by_ne_kpi_time_range(
        ne_id=impact_event.ne_id,
        kpi_name=kpi_name,
        start_time=windows.pre_window.start,
        end_time=windows.pre_window.end,
    )
    post_records = repository.find_by_ne_kpi_time_range(
        ne_id=impact_event.ne_id,
        kpi_name=kpi_name,
        start_time=windows.post_window.start,
        end_time=windows.post_window.end,
    )

    return ImpactDataLoadResult(
        ne_id=impact_event.ne_id,
        kpi_name=kpi_name,
        day_period=impact_day_period,
        week_profile=impact_week_profile,
        pre_window=_build_sample_window(
            records=pre_records,
            time_window=windows.pre_window,
            day_period=impact_day_period,
            week_profile=impact_week_profile,
            granularity_minutes=resolved_granularity_minutes,
            day_periods=resolved_day_periods,
        ),
        post_window=_build_sample_window(
            records=post_records,
            time_window=windows.post_window,
            day_period=impact_day_period,
            week_profile=impact_week_profile,
            granularity_minutes=resolved_granularity_minutes,
            day_periods=resolved_day_periods,
        ),
    )


def _build_sample_window(
    *,
    records: list[SupportsKPIRecord],
    time_window: TimeWindow,
    day_period: str,
    week_profile: str,
    granularity_minutes: int,
    day_periods: DayPeriodSettings,
) -> ImpactSampleWindow:
    clean_records = [
        record
        for record in records
        if _is_matching_bucket(
            record,
            day_period=day_period,
            week_profile=week_profile,
            day_periods=day_periods,
        )
        and _is_clean_record(record)
    ]
    expected_count = _count_expected_samples(
        time_window=time_window,
        day_period=day_period,
        week_profile=week_profile,
        granularity_minutes=granularity_minutes,
        day_periods=day_periods,
    )
    clean_count = len(clean_records)
    completeness = clean_count / expected_count if expected_count else 0.0
    return ImpactSampleWindow(
        records=clean_records,
        expected_count=expected_count,
        clean_count=clean_count,
        completeness=completeness,
        status="ready" if completeness >= MINIMUM_COMPLETENESS else "insufficient",
        time_window=time_window,
    )


def _is_matching_bucket(
    record: SupportsKPIRecord,
    *,
    day_period: str,
    week_profile: str,
    day_periods: DayPeriodSettings,
) -> bool:
    return (
        classify_day_period(
            _normalize_timestamp(record.start_time),
            day_periods=day_periods,
        ).period
        == day_period
        and classify_week_profile(_normalize_timestamp(record.start_time)).profile == week_profile
    )


def _is_clean_record(record: SupportsKPIRecord) -> bool:
    quality_flag = (record.quality_flag or "").strip().lower()
    return not record.is_noise and quality_flag == "good"


def _count_expected_samples(
    *,
    time_window: TimeWindow,
    day_period: str,
    week_profile: str,
    granularity_minutes: int,
    day_periods: DayPeriodSettings,
) -> int:
    step = timedelta(minutes=granularity_minutes)
    cursor = time_window.start
    expected = 0

    while cursor < time_window.end:
        if (
            classify_day_period(
                _normalize_timestamp(cursor),
                day_periods=day_periods,
            ).period
            == day_period
            and classify_week_profile(_normalize_timestamp(cursor)).profile == week_profile
        ):
            expected += 1
        cursor += step

    return expected


def _normalize_timestamp(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp
