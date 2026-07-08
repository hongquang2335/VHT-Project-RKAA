"""Detect logical duplicate KPI records within an input batch."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol


class SupportsDuplicateKey(Protocol):
    """Minimal contract required to evaluate KPI duplicate keys."""

    ne_id: str
    kpi_name: str
    start_time: datetime


@dataclass(frozen=True, slots=True)
class DuplicateCheckResult:
    """Represents a duplicate record discovered in a sequence."""

    record_index: int
    duplicate_of_index: int
    ne_id: str
    kpi_name: str
    start_time: datetime
    is_noise: bool
    noise_reason: str


def detect_duplicate_records(
    records: Iterable[SupportsDuplicateKey],
) -> list[DuplicateCheckResult]:
    """Return all records whose logical key repeats within the input order."""

    first_seen_by_key: dict[tuple[str, str, datetime], int] = {}
    duplicates: list[DuplicateCheckResult] = []

    for index, record in enumerate(records):
        key = (record.ne_id, record.kpi_name, record.start_time)
        first_seen_index = first_seen_by_key.get(key)

        if first_seen_index is None:
            first_seen_by_key[key] = index
            continue

        duplicates.append(
            DuplicateCheckResult(
                record_index=index,
                duplicate_of_index=first_seen_index,
                ne_id=record.ne_id,
                kpi_name=record.kpi_name,
                start_time=record.start_time,
                is_noise=True,
                noise_reason="duplicate_record",
            )
        )

    return duplicates
