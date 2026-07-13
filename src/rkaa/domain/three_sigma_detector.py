"""Detect KPI anomalies using the classic three-sigma rule."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

SIGMA_MULTIPLIER = 3.0


class SupportsBaselineStatistics(Protocol):
    """Minimal baseline contract required for three-sigma detection."""

    mean_value: float
    std_value: float


@dataclass(frozen=True, slots=True)
class ThreeSigmaDetectionResult:
    """Three-sigma classification for a single KPI value."""

    lower_bound: float
    upper_bound: float
    anomaly_flag: str
    is_anomalous: bool


def detect_three_sigma_anomaly(
    *,
    value: float,
    baseline: SupportsBaselineStatistics,
) -> ThreeSigmaDetectionResult:
    """Classify one KPI value as anomalous or normal using mean +/- 3 * std."""

    if baseline.std_value < 0:
        raise ValueError("baseline std_value must be non-negative.")

    sigma_span = SIGMA_MULTIPLIER * baseline.std_value
    lower_bound = baseline.mean_value - sigma_span
    upper_bound = baseline.mean_value + sigma_span
    if baseline.std_value == 0:
        is_anomalous = value != baseline.mean_value
    else:
        is_anomalous = value <= lower_bound or value >= upper_bound

    return ThreeSigmaDetectionResult(
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        anomaly_flag="anomalous" if is_anomalous else "normal",
        is_anomalous=is_anomalous,
    )
