"""Detect KPI anomalies by comparing values against baseline Z-scores."""

from __future__ import annotations

from dataclasses import dataclass
from math import inf
from typing import Protocol

from rkaa.core.config import ConfigError, load_settings

DEFAULT_ZSCORE_THRESHOLD = 3.0


class SupportsBaselineStatistics(Protocol):
    """Minimal baseline contract required for Z-score detection."""

    mean_value: float
    std_value: float


@dataclass(frozen=True, slots=True)
class ZScoreDetectionResult:
    """Z-score classification for a single KPI value."""

    z_score: float
    threshold: float
    anomaly_flag: str
    is_anomalous: bool


def detect_zscore_anomaly(
    *,
    value: float,
    baseline: SupportsBaselineStatistics,
    threshold: float | None = None,
) -> ZScoreDetectionResult:
    """Classify one KPI value as anomalous or normal using baseline Z-score."""

    resolved_threshold = _resolve_zscore_threshold(threshold)

    if baseline.std_value < 0:
        raise ValueError("baseline std_value must be non-negative.")

    if baseline.std_value == 0:
        z_score = 0.0 if value == baseline.mean_value else inf
    else:
        z_score = (value - baseline.mean_value) / baseline.std_value

    is_anomalous = abs(z_score) >= resolved_threshold
    return ZScoreDetectionResult(
        z_score=z_score,
        threshold=resolved_threshold,
        anomaly_flag="anomalous" if is_anomalous else "normal",
        is_anomalous=is_anomalous,
    )


def _resolve_zscore_threshold(threshold: float | None) -> float:
    if threshold is not None:
        _validate_threshold(threshold)
        return threshold

    try:
        resolved = load_settings().app.anomaly_zscore_threshold
    except ConfigError:
        return DEFAULT_ZSCORE_THRESHOLD

    _validate_threshold(resolved)
    return resolved


def _validate_threshold(threshold: float) -> None:
    if threshold <= 0:
        raise ValueError("threshold must be a positive number.")
