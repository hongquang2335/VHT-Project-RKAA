from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from rkaa.domain.maintenance_filter import (
    MaintenanceFilterResult,
    mark_records_in_maintenance,
)


@dataclass(frozen=True, slots=True)
class KPIRecordWindow:
    ne_id: str
    start_time: datetime
    end_time: datetime


@dataclass(frozen=True, slots=True)
class MaintenanceWindowStub:
    ne_id: str
    start_time: datetime
    end_time: datetime
    event_type: str


def _record(
    *,
    ne_id: str = "NE-001",
    start_minutes: int = 0,
    duration_minutes: int = 15,
) -> KPIRecordWindow:
    start = datetime(2026, 7, 8, 0, 0, tzinfo=UTC) + timedelta(minutes=start_minutes)
    return KPIRecordWindow(
        ne_id=ne_id,
        start_time=start,
        end_time=start + timedelta(minutes=duration_minutes),
    )


def _window(
    *,
    ne_id: str = "NE-001",
    start_minutes: int = 0,
    duration_minutes: int = 60,
    event_type: str = "software_upgrade",
) -> MaintenanceWindowStub:
    start = datetime(2026, 7, 8, 0, 0, tzinfo=UTC) + timedelta(minutes=start_minutes)
    return MaintenanceWindowStub(
        ne_id=ne_id,
        start_time=start,
        end_time=start + timedelta(minutes=duration_minutes),
        event_type=event_type,
    )


def test_mark_records_in_maintenance_marks_overlapping_records() -> None:
    records = [_record(start_minutes=15), _record(start_minutes=90)]
    windows = [_window(start_minutes=0, duration_minutes=60)]

    assert mark_records_in_maintenance(records, windows) == [
        MaintenanceFilterResult(
            record_index=0,
            is_maintenance=True,
            maintenance_reason="maintenance_window",
            matched_event_type="software_upgrade",
        )
    ]


def test_mark_records_in_maintenance_ignores_different_network_elements() -> None:
    records = [_record(ne_id="NE-002", start_minutes=15)]
    windows = [_window(ne_id="NE-001", start_minutes=0, duration_minutes=60)]

    assert mark_records_in_maintenance(records, windows) == []


def test_mark_records_in_maintenance_treats_touching_boundaries_as_non_overlapping() -> None:
    records = [_record(start_minutes=60, duration_minutes=15)]
    windows = [_window(start_minutes=0, duration_minutes=60)]

    assert mark_records_in_maintenance(records, windows) == []


def test_mark_records_in_maintenance_marks_partial_overlap() -> None:
    records = [_record(start_minutes=50, duration_minutes=20)]
    windows = [_window(start_minutes=0, duration_minutes=60, event_type="site_visit")]

    assert mark_records_in_maintenance(records, windows) == [
        MaintenanceFilterResult(
            record_index=0,
            is_maintenance=True,
            maintenance_reason="maintenance_window",
            matched_event_type="site_visit",
        )
    ]


def test_mark_records_in_maintenance_marks_multiple_records() -> None:
    records = [
        _record(start_minutes=5),
        _record(start_minutes=30),
        _record(start_minutes=120),
    ]
    windows = [_window(start_minutes=0, duration_minutes=60)]

    assert mark_records_in_maintenance(records, windows) == [
        MaintenanceFilterResult(
            record_index=0,
            is_maintenance=True,
            maintenance_reason="maintenance_window",
            matched_event_type="software_upgrade",
        ),
        MaintenanceFilterResult(
            record_index=1,
            is_maintenance=True,
            maintenance_reason="maintenance_window",
            matched_event_type="software_upgrade",
        ),
    ]
