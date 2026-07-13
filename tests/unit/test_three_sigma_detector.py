from __future__ import annotations

from dataclasses import dataclass

import pytest

from rkaa.domain.three_sigma_detector import (
    SIGMA_MULTIPLIER,
    ThreeSigmaDetectionResult,
    detect_three_sigma_anomaly,
)


@dataclass(frozen=True, slots=True)
class BaselineStub:
    mean_value: float
    std_value: float


def test_detect_three_sigma_anomaly_returns_normal_within_bounds() -> None:
    result = detect_three_sigma_anomaly(
        value=103.0,
        baseline=BaselineStub(mean_value=100.0, std_value=2.0),
    )

    assert result == ThreeSigmaDetectionResult(
        lower_bound=94.0,
        upper_bound=106.0,
        anomaly_flag="normal",
        is_anomalous=False,
    )


def test_detect_three_sigma_anomaly_marks_lower_boundary_as_anomalous() -> None:
    result = detect_three_sigma_anomaly(
        value=94.0,
        baseline=BaselineStub(mean_value=100.0, std_value=2.0),
    )

    assert result == ThreeSigmaDetectionResult(
        lower_bound=94.0,
        upper_bound=106.0,
        anomaly_flag="anomalous",
        is_anomalous=True,
    )


def test_detect_three_sigma_anomaly_marks_upper_boundary_as_anomalous() -> None:
    result = detect_three_sigma_anomaly(
        value=106.0,
        baseline=BaselineStub(mean_value=100.0, std_value=2.0),
    )

    assert result == ThreeSigmaDetectionResult(
        lower_bound=94.0,
        upper_bound=106.0,
        anomaly_flag="anomalous",
        is_anomalous=True,
    )


def test_detect_three_sigma_anomaly_handles_zero_std_with_matching_value() -> None:
    result = detect_three_sigma_anomaly(
        value=100.0,
        baseline=BaselineStub(mean_value=100.0, std_value=0.0),
    )

    assert result == ThreeSigmaDetectionResult(
        lower_bound=100.0,
        upper_bound=100.0,
        anomaly_flag="normal",
        is_anomalous=False,
    )


def test_detect_three_sigma_anomaly_handles_zero_std_with_changed_value() -> None:
    result = detect_three_sigma_anomaly(
        value=101.0,
        baseline=BaselineStub(mean_value=100.0, std_value=0.0),
    )

    assert result == ThreeSigmaDetectionResult(
        lower_bound=100.0,
        upper_bound=100.0,
        anomaly_flag="anomalous",
        is_anomalous=True,
    )


def test_detect_three_sigma_anomaly_uses_three_sigma_bounds() -> None:
    result = detect_three_sigma_anomaly(
        value=100.0,
        baseline=BaselineStub(mean_value=50.0, std_value=10.0),
    )

    assert result.lower_bound == 50.0 - (SIGMA_MULTIPLIER * 10.0)
    assert result.upper_bound == 50.0 + (SIGMA_MULTIPLIER * 10.0)


def test_detect_three_sigma_anomaly_rejects_negative_std() -> None:
    with pytest.raises(ValueError, match="baseline std_value must be non-negative."):
        detect_three_sigma_anomaly(
            value=100.0,
            baseline=BaselineStub(mean_value=100.0, std_value=-1.0),
        )
