"""Detect counter resets in KPI time series."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol


class SupportsCounterDefinition(Protocol):
    """Minimal KPI definition contract required for counter reset checks."""

    data_type: str


class SupportsCounterPoint(Protocol):
    """Minimal time-series point contract required for counter reset checks."""

    start_time: datetime
    value: float


@dataclass(frozen=True, slots=True)
class CounterResetResult:
    """Represents a detected counter reset event."""

    record_index: int
    timestamp: datetime
    previous_value: float
    current_value: float
    reason: str


def detect_counter_resets(
    records: Iterable[SupportsCounterPoint],
    kpi_definition: SupportsCounterDefinition,
) -> list[CounterResetResult]:
    """Detect drops in monotonic counters; ignore non-counter KPIs."""

    if kpi_definition.data_type != "counter":
        return []

    indexed_records = list(enumerate(records))
    ordered_records = sorted(indexed_records, key=lambda item: item[1].start_time)

    resets: list[CounterResetResult] = []
    for previous, current in zip(ordered_records, ordered_records[1:]):
        previous_index, previous_record = previous
        current_index, current_record = current
        if current_record.value >= previous_record.value:
            continue

        resets.append(
            CounterResetResult(
                record_index=current_index,
                timestamp=current_record.start_time,
                previous_value=previous_record.value,
                current_value=current_record.value,
                reason="counter_reset",
            )
        )

    return resets
