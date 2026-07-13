"""Detect threshold-based KPI anomalies from configured KPI metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class SupportsThresholdDefinition(Protocol):
    """Minimal KPI definition contract required for threshold detection."""

    direction_preference: str
    warning_threshold: float | None
    critical_threshold: float | None


@dataclass(frozen=True, slots=True)
class ThresholdDetectionResult:
    """Threshold classification for a single KPI value."""

    anomaly_flag: str


def detect_threshold_anomaly(
    *,
    value: float,
    kpi_definition: SupportsThresholdDefinition,
) -> ThresholdDetectionResult:
    """Classify one KPI value as normal, warning, critical, or not_evaluated."""

    warning_threshold = kpi_definition.warning_threshold
    critical_threshold = kpi_definition.critical_threshold
    if warning_threshold is None or critical_threshold is None:
        return ThresholdDetectionResult(anomaly_flag="not_evaluated")

    direction_preference = kpi_definition.direction_preference
    if direction_preference == "higher_is_better":
        if critical_threshold > warning_threshold:
            raise ValueError("higher_is_better requires critical_threshold <= warning_threshold.")
        if value <= critical_threshold:
            return ThresholdDetectionResult(anomaly_flag="critical")
        if value <= warning_threshold:
            return ThresholdDetectionResult(anomaly_flag="warning")
        return ThresholdDetectionResult(anomaly_flag="normal")

    if direction_preference == "lower_is_better":
        if critical_threshold < warning_threshold:
            raise ValueError("lower_is_better requires critical_threshold >= warning_threshold.")
        if value >= critical_threshold:
            return ThresholdDetectionResult(anomaly_flag="critical")
        if value >= warning_threshold:
            return ThresholdDetectionResult(anomaly_flag="warning")
        return ThresholdDetectionResult(anomaly_flag="normal")

    if direction_preference == "context_dependent":
        if critical_threshold > warning_threshold:
            if value >= critical_threshold:
                return ThresholdDetectionResult(anomaly_flag="critical")
            if value >= warning_threshold:
                return ThresholdDetectionResult(anomaly_flag="warning")
            return ThresholdDetectionResult(anomaly_flag="normal")

        if value <= critical_threshold:
            return ThresholdDetectionResult(anomaly_flag="critical")
        if value <= warning_threshold:
            return ThresholdDetectionResult(anomaly_flag="warning")
        return ThresholdDetectionResult(anomaly_flag="normal")

    raise ValueError(f"Unsupported direction_preference '{direction_preference}'.")
