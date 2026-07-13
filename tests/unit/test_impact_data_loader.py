from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from rkaa.core.config import DayPeriodSettings
from rkaa.domain.impact_data_loader import load_impact_kpi_samples


@dataclass(frozen=True, slots=True)
class ImpactEventStub:
    ne_id: str
    t1: datetime
    t2: datetime | None


@dataclass(frozen=True, slots=True)
class KPIRecordStub:
    ne_id: str
    kpi_name: str
    start_time: datetime
    end_time: datetime
    value: float
    quality_flag: str | None = "good"
    is_noise: bool = False


class KPIRecordRepositoryStub:
    def __init__(self, records: list[KPIRecordStub]) -> None:
        self._records = records

    def find_by_ne_kpi_time_range(
        self,
        *,
        ne_id: str,
        kpi_name: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[KPIRecordStub]:
        return [
            record
            for record in self._records
            if record.ne_id == ne_id
            and record.kpi_name == kpi_name
            and start_time <= record.start_time < end_time
        ]


def _day_periods() -> DayPeriodSettings:
    return DayPeriodSettings.model_validate(
        {
            "busy": {"start": "07:00", "end": "10:00"},
            "transition": {"start": "10:00", "end": "17:00"},
            "off_peak": {"start": "17:00", "end": "07:00"},
        }
    )


def _record(start_time: datetime, *, value: float, **kwargs: object) -> KPIRecordStub:
    return KPIRecordStub(
        ne_id="NE-001",
        kpi_name="erab_success_rate",
        start_time=start_time,
        end_time=start_time + timedelta(minutes=15),
        value=value,
        **kwargs,
    )


def test_load_impact_kpi_samples_keeps_only_clean_records_in_matching_bucket() -> None:
    impact_event = ImpactEventStub(
        ne_id="NE-001",
        t1=datetime(2026, 7, 6, 19, 0, tzinfo=UTC),
        t2=datetime(2026, 7, 6, 20, 0, tzinfo=UTC),
    )
    records = [
        _record(datetime(2026, 7, 6, 17, 0, tzinfo=UTC), value=98.0),
        _record(datetime(2026, 7, 6, 17, 15, tzinfo=UTC), value=97.5, quality_flag="bad"),
        _record(datetime(2026, 7, 6, 17, 30, tzinfo=UTC), value=97.2, is_noise=True),
        _record(datetime(2026, 7, 7, 2, 0, tzinfo=UTC), value=95.0),
        _record(datetime(2026, 7, 7, 2, 15, tzinfo=UTC), value=94.5),
        _record(datetime(2026, 7, 6, 17, 45, tzinfo=UTC), value=70.0, quality_flag="good"),
    ]

    result = load_impact_kpi_samples(
        impact_event=impact_event,
        kpi_name="erab_success_rate",
        repository=KPIRecordRepositoryStub(records),
        pre_window_hours=2,
        recovery_buffer_hours=4,
        post_window_hours=2,
        granularity_minutes=15,
        day_periods=_day_periods(),
    )

    assert result.day_period == "off_peak"
    assert result.week_profile == "weekday"
    assert [record.start_time for record in result.pre_window.records] == [
        datetime(2026, 7, 6, 17, 0, tzinfo=UTC),
        datetime(2026, 7, 6, 17, 45, tzinfo=UTC),
    ]
    assert [record.start_time for record in result.post_window.records] == [
        datetime(2026, 7, 7, 2, 0, tzinfo=UTC),
        datetime(2026, 7, 7, 2, 15, tzinfo=UTC),
    ]


def test_load_impact_kpi_samples_marks_window_insufficient_below_70_percent_completeness() -> None:
    impact_event = ImpactEventStub(
        ne_id="NE-001",
        t1=datetime(2026, 7, 6, 19, 0, tzinfo=UTC),
        t2=datetime(2026, 7, 6, 20, 0, tzinfo=UTC),
    )
    records = [
        _record(datetime(2026, 7, 6, 17, 0, tzinfo=UTC), value=98.0),
        _record(datetime(2026, 7, 6, 17, 15, tzinfo=UTC), value=97.8),
        _record(datetime(2026, 7, 6, 17, 30, tzinfo=UTC), value=97.6),
        _record(datetime(2026, 7, 7, 2, 0, tzinfo=UTC), value=95.0),
        _record(datetime(2026, 7, 7, 2, 15, tzinfo=UTC), value=94.8),
    ]

    result = load_impact_kpi_samples(
        impact_event=impact_event,
        kpi_name="erab_success_rate",
        repository=KPIRecordRepositoryStub(records),
        pre_window_hours=2,
        recovery_buffer_hours=4,
        post_window_hours=2,
        granularity_minutes=15,
        day_periods=_day_periods(),
    )

    assert result.pre_window.expected_count == 8
    assert result.pre_window.clean_count == 3
    assert result.pre_window.completeness == 0.375
    assert result.pre_window.status == "insufficient"
    assert result.post_window.expected_count == 8
    assert result.post_window.clean_count == 2
    assert result.post_window.status == "insufficient"


def test_load_impact_kpi_samples_marks_window_ready_at_70_percent_or_above() -> None:
    impact_event = ImpactEventStub(
        ne_id="NE-001",
        t1=datetime(2026, 7, 6, 19, 0, tzinfo=UTC),
        t2=datetime(2026, 7, 6, 20, 0, tzinfo=UTC),
    )
    pre_records = [
        _record(datetime(2026, 7, 6, 17, minute, tzinfo=UTC), value=98.0 - index)
        for index, minute in enumerate((0, 15, 30, 45))
    ]
    pre_records.extend(
        _record(datetime(2026, 7, 6, 18, minute, tzinfo=UTC), value=94.0 - index)
        for index, minute in enumerate((0, 15, 30))
    )
    post_records = [
        _record(datetime(2026, 7, 7, 2, minute, tzinfo=UTC), value=95.0 - index)
        for index, minute in enumerate((0, 15, 30, 45))
    ]
    post_records.extend(
        _record(datetime(2026, 7, 7, 3, minute, tzinfo=UTC), value=91.0 - index)
        for index, minute in enumerate((0, 15, 30))
    )

    result = load_impact_kpi_samples(
        impact_event=impact_event,
        kpi_name="erab_success_rate",
        repository=KPIRecordRepositoryStub(pre_records + post_records),
        pre_window_hours=2,
        recovery_buffer_hours=4,
        post_window_hours=2,
        granularity_minutes=15,
        day_periods=_day_periods(),
    )

    assert result.pre_window.expected_count == 8
    assert result.pre_window.clean_count == 7
    assert result.pre_window.completeness == 0.875
    assert result.pre_window.status == "ready"
    assert result.post_window.expected_count == 8
    assert result.post_window.clean_count == 7
    assert result.post_window.completeness == 0.875
    assert result.post_window.status == "ready"
