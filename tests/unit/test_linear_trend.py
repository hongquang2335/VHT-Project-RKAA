from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from rkaa.domain.linear_trend import LinearTrendResult, calculate_linear_trend


@dataclass(frozen=True, slots=True)
class TrendPoint:
    start_time: datetime
    value: float


def test_calculate_linear_trend_returns_expected_metrics_for_perfect_increase() -> None:
    base_time = datetime(2026, 7, 11, 0, 0, tzinfo=UTC)

    result = calculate_linear_trend(
        [
            TrendPoint(start_time=base_time + timedelta(minutes=15 * index), value=value)
            for index, value in enumerate([10.0, 12.0, 14.0, 16.0])
        ]
    )

    assert result == LinearTrendResult(slope=2.0, intercept=10.0, r_squared=1.0)


def test_calculate_linear_trend_sorts_samples_by_start_time() -> None:
    base_time = datetime(2026, 7, 11, 0, 0, tzinfo=UTC)

    result = calculate_linear_trend(
        [
            TrendPoint(start_time=base_time + timedelta(minutes=30), value=14.0),
            TrendPoint(start_time=base_time, value=10.0),
            TrendPoint(start_time=base_time + timedelta(minutes=15), value=12.0),
        ]
    )

    assert result == LinearTrendResult(slope=2.0, intercept=10.0, r_squared=1.0)


def test_calculate_linear_trend_returns_zero_slope_for_flat_series() -> None:
    base_time = datetime(2026, 7, 11, 0, 0, tzinfo=UTC)

    result = calculate_linear_trend(
        [
            TrendPoint(start_time=base_time + timedelta(minutes=15 * index), value=42.0)
            for index in range(4)
        ]
    )

    assert result == LinearTrendResult(slope=0.0, intercept=42.0, r_squared=1.0)


def test_calculate_linear_trend_returns_single_point_line_for_one_sample() -> None:
    sample = TrendPoint(
        start_time=datetime(2026, 7, 11, 0, 0, tzinfo=UTC),
        value=7.5,
    )

    result = calculate_linear_trend([sample])

    assert result == LinearTrendResult(slope=0.0, intercept=7.5, r_squared=1.0)


def test_calculate_linear_trend_returns_partial_fit_for_noisy_series() -> None:
    base_time = datetime(2026, 7, 11, 0, 0, tzinfo=UTC)

    result = calculate_linear_trend(
        [
            TrendPoint(start_time=base_time + timedelta(minutes=15 * index), value=value)
            for index, value in enumerate([10.0, 13.0, 13.0, 16.0])
        ]
    )

    assert result.slope == pytest.approx(1.8)
    assert result.intercept == pytest.approx(10.3)
    assert result.r_squared == pytest.approx(0.9)


def test_calculate_linear_trend_rejects_empty_samples() -> None:
    with pytest.raises(ValueError, match="samples must contain at least one point."):
        calculate_linear_trend([])
