from __future__ import annotations

from dataclasses import dataclass

import pytest

from rkaa.domain.delta_calculator import DeltaCalculationResult, calculate_delta


@dataclass(frozen=True, slots=True)
class Sample:
    value: float


def test_calculate_delta_returns_pre_post_means_and_deltas() -> None:
    result = calculate_delta(
        pre_samples=[Sample(98.0), Sample(100.0), Sample(96.0)],
        post_samples=[Sample(93.0), Sample(95.0), Sample(94.0)],
    )

    assert result == DeltaCalculationResult(
        pre_mean=98.0,
        post_mean=94.0,
        delta_abs=-4.0,
        delta_pct=pytest.approx(-4.081632653061225),
    )


def test_calculate_delta_handles_zero_pre_mean_safely() -> None:
    result = calculate_delta(
        pre_samples=[Sample(0.0), Sample(0.0)],
        post_samples=[Sample(5.0), Sample(7.0)],
    )

    assert result == DeltaCalculationResult(
        pre_mean=0.0,
        post_mean=6.0,
        delta_abs=6.0,
        delta_pct=0.0,
    )


def test_calculate_delta_rejects_empty_pre_samples() -> None:
    with pytest.raises(ValueError, match="pre_samples must contain at least one value."):
        calculate_delta(
            pre_samples=[],
            post_samples=[Sample(1.0)],
        )


def test_calculate_delta_rejects_empty_post_samples() -> None:
    with pytest.raises(ValueError, match="post_samples must contain at least one value."):
        calculate_delta(
            pre_samples=[Sample(1.0)],
            post_samples=[],
        )
