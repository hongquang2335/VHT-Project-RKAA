"""Mark KPI records that fall within maintenance windows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol


class SupportsRecordWindow(Protocol):
    """Minimal KPI record contract required for maintenance filtering."""

    ne_id: str
    start_time: datetime
    end_time: datetime


class SupportsMaintenanceWindow(Protocol):
    """Minimal maintenance window contract required for overlap checks."""

    ne_id: str
    start_time: datetime
    end_time: datetime
    event_type: str


@dataclass(frozen=True, slots=True)
class MaintenanceFilterResult:
    """Represents a record marked as inside a maintenance window."""

    record_index: int
    is_maintenance: bool
    maintenance_reason: str
    matched_event_type: str


def mark_records_in_maintenance(
    records: Iterable[SupportsRecordWindow],
    maintenance_windows: Iterable[SupportsMaintenanceWindow],
) -> list[MaintenanceFilterResult]:
    """Mark records that overlap a maintenance window for the same NE."""

    indexed_records = list(enumerate(records))
    windows = list(maintenance_windows)
    results: list[MaintenanceFilterResult] = []

    for index, record in indexed_records:
        matched_window = next(
            (
                window
                for window in windows
                if window.ne_id == record.ne_id and _overlaps(record, window)
            ),
            None,
        )
        if matched_window is None:
            continue

        results.append(
            MaintenanceFilterResult(
                record_index=index,
                is_maintenance=True,
                maintenance_reason="maintenance_window",
                matched_event_type=matched_window.event_type,
            )
        )

    return results


def _overlaps(
    record: SupportsRecordWindow,
    maintenance_window: SupportsMaintenanceWindow,
) -> bool:
    return (
        record.start_time < maintenance_window.end_time
        and record.end_time > maintenance_window.start_time
    )
