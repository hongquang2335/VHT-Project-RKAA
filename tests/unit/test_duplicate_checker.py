from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from rkaa.domain.noise_filter.duplicate_checker import (
    DuplicateCheckResult,
    detect_duplicate_records,
)


@dataclass(frozen=True, slots=True)
class KPIRecordCandidate:
    ne_id: str
    kpi_name: str
    start_time: datetime


def _make_record(
    *,
    ne_id: str = "NE-001",
    kpi_name: str = "availability",
    start_time: datetime | None = None,
) -> KPIRecordCandidate:
    return KPIRecordCandidate(
        ne_id=ne_id,
        kpi_name=kpi_name,
        start_time=start_time or datetime(2026, 7, 7, 0, 0, tzinfo=UTC),
    )


def test_detect_duplicate_records_returns_empty_for_unique_keys() -> None:
    start = datetime(2026, 7, 7, 0, 0, tzinfo=UTC)
    records = [
        _make_record(start_time=start),
        _make_record(start_time=start + timedelta(minutes=15)),
        _make_record(ne_id="NE-002", start_time=start),
        _make_record(kpi_name="throughput", start_time=start),
    ]

    assert detect_duplicate_records(records) == []


def test_detect_duplicate_records_flags_later_occurrence_of_same_key() -> None:
    start = datetime(2026, 7, 7, 0, 0, tzinfo=UTC)
    records = [
        _make_record(start_time=start),
        _make_record(start_time=start + timedelta(minutes=15)),
        _make_record(start_time=start),
    ]

    assert detect_duplicate_records(records) == [
        DuplicateCheckResult(
            record_index=2,
            duplicate_of_index=0,
            ne_id="NE-001",
            kpi_name="availability",
            start_time=start,
            is_noise=True,
            noise_reason="duplicate_record",
        )
    ]


def test_detect_duplicate_records_flags_each_repeated_occurrence() -> None:
    start = datetime(2026, 7, 7, 0, 0, tzinfo=UTC)
    records = [
        _make_record(start_time=start),
        _make_record(start_time=start),
        _make_record(start_time=start),
    ]

    assert detect_duplicate_records(records) == [
        DuplicateCheckResult(
            record_index=1,
            duplicate_of_index=0,
            ne_id="NE-001",
            kpi_name="availability",
            start_time=start,
            is_noise=True,
            noise_reason="duplicate_record",
        ),
        DuplicateCheckResult(
            record_index=2,
            duplicate_of_index=0,
            ne_id="NE-001",
            kpi_name="availability",
            start_time=start,
            is_noise=True,
            noise_reason="duplicate_record",
        ),
    ]


def test_detect_duplicate_records_distinguishes_key_components() -> None:
    start = datetime(2026, 7, 7, 0, 0, tzinfo=UTC)
    records = [
        _make_record(ne_id="NE-001", kpi_name="availability", start_time=start),
        _make_record(ne_id="NE-001", kpi_name="throughput", start_time=start),
        _make_record(ne_id="NE-002", kpi_name="availability", start_time=start),
        _make_record(
            ne_id="NE-001",
            kpi_name="availability",
            start_time=start + timedelta(minutes=15),
        ),
    ]

    assert detect_duplicate_records(records) == []
