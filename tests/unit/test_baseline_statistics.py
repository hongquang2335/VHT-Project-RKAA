from __future__ import annotations

import math

import pytest

from rkaa.domain.baseline_statistics import (
    BaselineStatistics,
    compute_baseline_statistics,
)


def test_compute_baseline_statistics_returns_expected_summary() -> None:
    result = compute_baseline_statistics([10.0, 20.0, 30.0, 40.0, 50.0])

    assert result == BaselineStatistics(
        mean=30.0,
        median=30.0,
        std=math.sqrt(200.0),
        p5=12.0,
        p95=48.0,
        sample_count=5,
    )


def test_compute_baseline_statistics_sorts_values_before_percentiles() -> None:
    result = compute_baseline_statistics([40.0, 10.0, 50.0, 20.0, 30.0])

    assert result.p5 == 12.0
    assert result.p95 == 48.0


def test_compute_baseline_statistics_uses_zero_std_for_single_sample() -> None:
    result = compute_baseline_statistics([42.0])

    assert result == BaselineStatistics(
        mean=42.0,
        median=42.0,
        std=0.0,
        p5=42.0,
        p95=42.0,
        sample_count=1,
    )


def test_compute_baseline_statistics_raises_for_empty_samples() -> None:
    with pytest.raises(ValueError, match="at least one sample"):
        compute_baseline_statistics([])
