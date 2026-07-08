from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from rkaa.core.config import ConfigError
from rkaa.domain.noise_filter.gap_detector import (
    GapDetectionResult,
    detect_time_series_gaps,
)


@dataclass(frozen=True, slots=True)
class KPIRecordPoint:
    start_time: datetime


def _make_point(start_time: datetime) -> KPIRecordPoint:
    return KPIRecordPoint(start_time=start_time)


def test_detect_time_series_gaps_returns_empty_for_contiguous_series() -> None:
    start = datetime(2026, 7, 7, 0, 0, tzinfo=UTC)
    records = [
        _make_point(start),
        _make_point(start + timedelta(minutes=15)),
        _make_point(start + timedelta(minutes=30)),
    ]

    assert detect_time_series_gaps(records, granularity_minutes=15) == []


def test_detect_time_series_gaps_reports_missing_periods() -> None:
    start = datetime(2026, 7, 7, 0, 0, tzinfo=UTC)
    records = [
        _make_point(start),
        _make_point(start + timedelta(minutes=45)),
    ]

    assert detect_time_series_gaps(records, granularity_minutes=15) == [
        GapDetectionResult(
            gap_start=start + timedelta(minutes=15),
            gap_end=start + timedelta(minutes=30),
            missing_periods=2,
            is_warning=False,
        )
    ]


def test_detect_time_series_gaps_sorts_input_before_detection() -> None:
    start = datetime(2026, 7, 7, 0, 0, tzinfo=UTC)
    records = [
        _make_point(start + timedelta(minutes=45)),
        _make_point(start),
    ]

    assert detect_time_series_gaps(records, granularity_minutes=15) == [
        GapDetectionResult(
            gap_start=start + timedelta(minutes=15),
            gap_end=start + timedelta(minutes=30),
            missing_periods=2,
            is_warning=False,
        )
    ]


def test_detect_time_series_gaps_marks_warning_for_gaps_longer_than_two_hours() -> None:
    start = datetime(2026, 7, 7, 0, 0, tzinfo=UTC)
    records = [
        _make_point(start),
        _make_point(start + timedelta(hours=2, minutes=30)),
    ]

    assert detect_time_series_gaps(records, granularity_minutes=15) == [
        GapDetectionResult(
            gap_start=start + timedelta(minutes=15),
            gap_end=start + timedelta(hours=2, minutes=15),
            missing_periods=9,
            is_warning=True,
        )
    ]


def test_detect_time_series_gaps_uses_configured_granularity_when_not_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "rkaa.domain.noise_filter.gap_detector.load_settings",
        lambda: SimpleNamespace(app=SimpleNamespace(granularity_minutes=30)),
    )
    start = datetime(2026, 7, 7, 0, 0, tzinfo=UTC)
    records = [
        _make_point(start),
        _make_point(start + timedelta(minutes=90)),
    ]

    assert detect_time_series_gaps(records) == [
        GapDetectionResult(
            gap_start=start + timedelta(minutes=30),
            gap_end=start + timedelta(minutes=60),
            missing_periods=2,
            is_warning=False,
        )
    ]


def test_detect_time_series_gaps_falls_back_to_default_granularity_when_config_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "rkaa.domain.noise_filter.gap_detector.load_settings",
        lambda: (_ for _ in ()).throw(ConfigError("missing config")),
    )
    start = datetime(2026, 7, 7, 0, 0, tzinfo=UTC)
    records = [
        _make_point(start),
        _make_point(start + timedelta(minutes=45)),
    ]

    assert detect_time_series_gaps(records) == [
        GapDetectionResult(
            gap_start=start + timedelta(minutes=15),
            gap_end=start + timedelta(minutes=30),
            missing_periods=2,
            is_warning=False,
        )
    ]


def test_detect_time_series_gaps_rejects_non_positive_granularity() -> None:
    with pytest.raises(ValueError, match="granularity_minutes must be a positive integer"):
        detect_time_series_gaps([], granularity_minutes=0)
