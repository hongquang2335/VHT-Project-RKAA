from __future__ import annotations

from dataclasses import dataclass

import pytest

from rkaa.domain.threshold_detector import (
    ThresholdDetectionResult,
    detect_threshold_anomaly,
)


@dataclass(frozen=True, slots=True)
class KPIDefinitionStub:
    direction_preference: str
    warning_threshold: float | None
    critical_threshold: float | None


def test_detect_threshold_anomaly_returns_not_evaluated_when_thresholds_are_missing() -> None:
    result = detect_threshold_anomaly(
        value=96.0,
        kpi_definition=KPIDefinitionStub(
            direction_preference="higher_is_better",
            warning_threshold=None,
            critical_threshold=95.0,
        ),
    )

    assert result == ThresholdDetectionResult(anomaly_flag="not_evaluated")


def test_detect_threshold_anomaly_uses_higher_is_better_thresholds() -> None:
    critical = detect_threshold_anomaly(
        value=95.0,
        kpi_definition=KPIDefinitionStub(
            direction_preference="higher_is_better",
            warning_threshold=97.0,
            critical_threshold=95.0,
        ),
    )
    warning = detect_threshold_anomaly(
        value=96.0,
        kpi_definition=KPIDefinitionStub(
            direction_preference="higher_is_better",
            warning_threshold=97.0,
            critical_threshold=95.0,
        ),
    )
    normal = detect_threshold_anomaly(
        value=98.0,
        kpi_definition=KPIDefinitionStub(
            direction_preference="higher_is_better",
            warning_threshold=97.0,
            critical_threshold=95.0,
        ),
    )

    assert critical == ThresholdDetectionResult(anomaly_flag="critical")
    assert warning == ThresholdDetectionResult(anomaly_flag="warning")
    assert normal == ThresholdDetectionResult(anomaly_flag="normal")


def test_detect_threshold_anomaly_uses_lower_is_better_thresholds() -> None:
    critical = detect_threshold_anomaly(
        value=40.0,
        kpi_definition=KPIDefinitionStub(
            direction_preference="lower_is_better",
            warning_threshold=30.0,
            critical_threshold=40.0,
        ),
    )
    warning = detect_threshold_anomaly(
        value=35.0,
        kpi_definition=KPIDefinitionStub(
            direction_preference="lower_is_better",
            warning_threshold=30.0,
            critical_threshold=40.0,
        ),
    )
    normal = detect_threshold_anomaly(
        value=20.0,
        kpi_definition=KPIDefinitionStub(
            direction_preference="lower_is_better",
            warning_threshold=30.0,
            critical_threshold=40.0,
        ),
    )

    assert critical == ThresholdDetectionResult(anomaly_flag="critical")
    assert warning == ThresholdDetectionResult(anomaly_flag="warning")
    assert normal == ThresholdDetectionResult(anomaly_flag="normal")


def test_detect_threshold_anomaly_supports_context_dependent_lower_values() -> None:
    result = detect_threshold_anomaly(
        value=54.0,
        kpi_definition=KPIDefinitionStub(
            direction_preference="context_dependent",
            warning_threshold=60.0,
            critical_threshold=55.0,
        ),
    )

    assert result == ThresholdDetectionResult(anomaly_flag="critical")


def test_detect_threshold_anomaly_supports_context_dependent_higher_values() -> None:
    result = detect_threshold_anomaly(
        value=86.0,
        kpi_definition=KPIDefinitionStub(
            direction_preference="context_dependent",
            warning_threshold=80.0,
            critical_threshold=85.0,
        ),
    )

    assert result == ThresholdDetectionResult(anomaly_flag="critical")


def test_detect_threshold_anomaly_rejects_invalid_higher_is_better_threshold_order() -> None:
    with pytest.raises(
        ValueError,
        match="higher_is_better requires critical_threshold <= warning_threshold.",
    ):
        detect_threshold_anomaly(
            value=100.0,
            kpi_definition=KPIDefinitionStub(
                direction_preference="higher_is_better",
                warning_threshold=95.0,
                critical_threshold=97.0,
            ),
        )


def test_detect_threshold_anomaly_rejects_invalid_lower_is_better_threshold_order() -> None:
    with pytest.raises(
        ValueError,
        match="lower_is_better requires critical_threshold >= warning_threshold.",
    ):
        detect_threshold_anomaly(
            value=0.0,
            kpi_definition=KPIDefinitionStub(
                direction_preference="lower_is_better",
                warning_threshold=40.0,
                critical_threshold=30.0,
            ),
        )


def test_detect_threshold_anomaly_rejects_unknown_direction_preference() -> None:
    with pytest.raises(ValueError, match="Unsupported direction_preference 'invalid'."):
        detect_threshold_anomaly(
            value=50.0,
            kpi_definition=KPIDefinitionStub(
                direction_preference="invalid",
                warning_threshold=40.0,
                critical_threshold=30.0,
            ),
        )
