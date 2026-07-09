from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from rkaa.domain.baseline_confidence import (
    BaselineConfidenceAssessment,
    assess_baseline_confidence,
)


@dataclass(frozen=True, slots=True)
class CleanSample:
    start_time: datetime


def _daily_records(day_count: int, *, samples_per_day: int = 1) -> list[CleanSample]:
    start = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    records: list[CleanSample] = []
    for day_offset in range(day_count):
        for sample_index in range(samples_per_day):
            records.append(
                CleanSample(
                    start_time=start + timedelta(days=day_offset, minutes=15 * sample_index)
                )
            )
    return records


def test_assess_baseline_confidence_returns_insufficient_below_threshold() -> None:
    result = assess_baseline_confidence(_daily_records(13), required_clean_days=14)

    assert result == BaselineConfidenceAssessment(
        status="insufficient",
        clean_day_count=13,
        required_day_count=14,
        is_reliable=False,
    )


def test_assess_baseline_confidence_returns_reliable_at_threshold() -> None:
    result = assess_baseline_confidence(_daily_records(14), required_clean_days=14)

    assert result == BaselineConfidenceAssessment(
        status="reliable",
        clean_day_count=14,
        required_day_count=14,
        is_reliable=True,
    )


def test_assess_baseline_confidence_counts_unique_days_only_once() -> None:
    result = assess_baseline_confidence(
        _daily_records(14, samples_per_day=4),
        required_clean_days=14,
    )

    assert result.clean_day_count == 14
    assert result.is_reliable is True


def test_assess_baseline_confidence_reads_required_days_from_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "rkaa.domain.baseline_confidence.load_settings",
        lambda: SimpleNamespace(app=SimpleNamespace(baseline_min_clean_days=10)),
    )

    result = assess_baseline_confidence(_daily_records(10))

    assert result.required_day_count == 10
    assert result.status == "reliable"


def test_assess_baseline_confidence_rejects_non_positive_threshold() -> None:
    with pytest.raises(ValueError, match="required_clean_days must be a positive integer"):
        assess_baseline_confidence(_daily_records(1), required_clean_days=0)
