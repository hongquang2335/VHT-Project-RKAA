from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from rkaa.domain.stl_decomposition import STLDecompositionResult, decompose_stl


@dataclass(frozen=True, slots=True)
class TimeSeriesPoint:
    start_time: datetime
    value: float


def test_decompose_stl_returns_components_for_flat_series() -> None:
    base_time = datetime(2026, 7, 11, 0, 0, tzinfo=UTC)
    samples = [
        TimeSeriesPoint(start_time=base_time + timedelta(minutes=15 * index), value=10.0)
        for index in range(4)
    ]

    result = decompose_stl(samples, season_length=2)

    assert result == STLDecompositionResult(
        timestamps=[sample.start_time for sample in samples],
        observed=[10.0, 10.0, 10.0, 10.0],
        trend=[10.0, 10.0, 10.0, 10.0],
        seasonal=[0.0, 0.0, 0.0, 0.0],
        residual=[0.0, 0.0, 0.0, 0.0],
    )


def test_decompose_stl_sorts_samples_by_start_time() -> None:
    base_time = datetime(2026, 7, 11, 0, 0, tzinfo=UTC)
    samples = [
        TimeSeriesPoint(start_time=base_time + timedelta(minutes=30), value=3.0),
        TimeSeriesPoint(start_time=base_time, value=1.0),
        TimeSeriesPoint(start_time=base_time + timedelta(minutes=15), value=2.0),
    ]

    result = decompose_stl(samples, season_length=2)

    assert result.timestamps == [
        base_time,
        base_time + timedelta(minutes=15),
        base_time + timedelta(minutes=30),
    ]
    assert result.observed == [1.0, 2.0, 3.0]


def test_decompose_stl_reconstructs_original_signal() -> None:
    base_time = datetime(2026, 7, 11, 0, 0, tzinfo=UTC)
    observed = [10.0, 13.0, 12.0, 15.0, 14.0, 17.0]
    samples = [
        TimeSeriesPoint(start_time=base_time + timedelta(minutes=15 * index), value=value)
        for index, value in enumerate(observed)
    ]

    result = decompose_stl(samples, season_length=2)

    reconstructed = [
        trend + seasonal + residual
        for trend, seasonal, residual in zip(result.trend, result.seasonal, result.residual)
    ]
    assert reconstructed == pytest.approx(observed)


def test_decompose_stl_extracts_repeating_seasonal_pattern() -> None:
    base_time = datetime(2026, 7, 11, 0, 0, tzinfo=UTC)
    observed = [11.0, 9.0, 11.0, 9.0, 11.0, 9.0]
    samples = [
        TimeSeriesPoint(start_time=base_time + timedelta(minutes=15 * index), value=value)
        for index, value in enumerate(observed)
    ]

    result = decompose_stl(samples, season_length=2)

    assert result.seasonal[0] == pytest.approx(result.seasonal[2])
    assert result.seasonal[1] == pytest.approx(result.seasonal[3])
    assert sum(result.seasonal[:2]) == pytest.approx(0.0)


def test_decompose_stl_rejects_invalid_season_length() -> None:
    with pytest.raises(ValueError, match="season_length must be greater than 1."):
        decompose_stl([], season_length=1)


def test_decompose_stl_requires_at_least_one_full_season() -> None:
    sample = TimeSeriesPoint(
        start_time=datetime(2026, 7, 11, 0, 0, tzinfo=UTC),
        value=5.0,
    )

    with pytest.raises(ValueError, match="at least one full season"):
        decompose_stl([sample], season_length=2)
