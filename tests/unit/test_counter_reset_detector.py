from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from rkaa.domain.noise_filter.counter_reset_detector import (
    CounterResetResult,
    detect_counter_resets,
)


@dataclass(frozen=True, slots=True)
class KPIDefinitionStub:
    data_type: str


@dataclass(frozen=True, slots=True)
class KPIRecordPoint:
    start_time: datetime
    value: float


def _make_point(*, minutes: int, value: float) -> KPIRecordPoint:
    return KPIRecordPoint(
        start_time=datetime(2026, 7, 7, 0, 0, tzinfo=UTC) + timedelta(minutes=minutes),
        value=value,
    )


def test_detect_counter_resets_returns_empty_for_non_counter_kpi() -> None:
    records = [_make_point(minutes=0, value=10.0), _make_point(minutes=15, value=5.0)]

    assert detect_counter_resets(records, KPIDefinitionStub(data_type="kpi")) == []


def test_detect_counter_resets_returns_empty_for_monotonic_counter() -> None:
    records = [
        _make_point(minutes=0, value=10.0),
        _make_point(minutes=15, value=10.0),
        _make_point(minutes=30, value=12.0),
    ]

    assert detect_counter_resets(records, KPIDefinitionStub(data_type="counter")) == []


def test_detect_counter_resets_flags_drop_in_counter_value() -> None:
    records = [
        _make_point(minutes=0, value=10.0),
        _make_point(minutes=15, value=25.0),
        _make_point(minutes=30, value=3.0),
    ]

    assert detect_counter_resets(records, KPIDefinitionStub(data_type="counter")) == [
        CounterResetResult(
            record_index=2,
            timestamp=_make_point(minutes=30, value=3.0).start_time,
            previous_value=25.0,
            current_value=3.0,
            reason="counter_reset",
        )
    ]


def test_detect_counter_resets_sorts_records_by_timestamp_before_comparison() -> None:
    records = [
        _make_point(minutes=30, value=3.0),
        _make_point(minutes=0, value=10.0),
        _make_point(minutes=15, value=25.0),
    ]

    assert detect_counter_resets(records, KPIDefinitionStub(data_type="counter")) == [
        CounterResetResult(
            record_index=0,
            timestamp=_make_point(minutes=30, value=3.0).start_time,
            previous_value=25.0,
            current_value=3.0,
            reason="counter_reset",
        )
    ]


def test_detect_counter_resets_flags_each_reset_event() -> None:
    records = [
        _make_point(minutes=0, value=100.0),
        _make_point(minutes=15, value=20.0),
        _make_point(minutes=30, value=30.0),
        _make_point(minutes=45, value=5.0),
    ]

    assert detect_counter_resets(records, KPIDefinitionStub(data_type="counter")) == [
        CounterResetResult(
            record_index=1,
            timestamp=_make_point(minutes=15, value=20.0).start_time,
            previous_value=100.0,
            current_value=20.0,
            reason="counter_reset",
        ),
        CounterResetResult(
            record_index=3,
            timestamp=_make_point(minutes=45, value=5.0).start_time,
            previous_value=30.0,
            current_value=5.0,
            reason="counter_reset",
        ),
    ]
