from __future__ import annotations

from rkaa.domain.anomaly_aggregation import (
    AggregatedAnomalyResult,
    aggregate_anomaly_results,
)
from rkaa.domain.three_sigma_detector import ThreeSigmaDetectionResult
from rkaa.domain.threshold_detector import ThresholdDetectionResult
from rkaa.domain.zscore_detector import ZScoreDetectionResult


def test_aggregate_anomaly_results_returns_not_evaluated_when_no_results_are_given() -> None:
    result = aggregate_anomaly_results()

    assert result == AggregatedAnomalyResult(
        is_anomaly=False,
        severity="not_evaluated",
        reasons=[],
    )


def test_aggregate_anomaly_results_prioritizes_critical_over_other_severities() -> None:
    result = aggregate_anomaly_results(
        threshold_result=ThresholdDetectionResult(anomaly_flag="critical"),
        zscore_result=ZScoreDetectionResult(
            z_score=3.5,
            threshold=3.0,
            anomaly_flag="anomalous",
            is_anomalous=True,
        ),
        three_sigma_result=ThreeSigmaDetectionResult(
            lower_bound=94.0,
            upper_bound=106.0,
            anomaly_flag="anomalous",
            is_anomalous=True,
        ),
    )

    assert result == AggregatedAnomalyResult(
        is_anomaly=True,
        severity="critical",
        reasons=["threshold_critical", "zscore_anomaly", "three_sigma_anomaly"],
    )


def test_aggregate_anomaly_results_keeps_warning_when_no_critical_exists() -> None:
    result = aggregate_anomaly_results(
        threshold_result=ThresholdDetectionResult(anomaly_flag="warning"),
        zscore_result=ZScoreDetectionResult(
            z_score=0.5,
            threshold=3.0,
            anomaly_flag="normal",
            is_anomalous=False,
        ),
    )

    assert result == AggregatedAnomalyResult(
        is_anomaly=True,
        severity="warning",
        reasons=["threshold_warning"],
    )


def test_aggregate_anomaly_results_uses_anomalous_when_statistical_detectors_fire() -> None:
    result = aggregate_anomaly_results(
        threshold_result=ThresholdDetectionResult(anomaly_flag="not_evaluated"),
        zscore_result=ZScoreDetectionResult(
            z_score=-3.2,
            threshold=3.0,
            anomaly_flag="anomalous",
            is_anomalous=True,
        ),
        three_sigma_result=ThreeSigmaDetectionResult(
            lower_bound=94.0,
            upper_bound=106.0,
            anomaly_flag="normal",
            is_anomalous=False,
        ),
    )

    assert result == AggregatedAnomalyResult(
        is_anomaly=True,
        severity="anomalous",
        reasons=["zscore_anomaly"],
    )


def test_aggregate_anomaly_results_returns_normal_when_all_evaluated_results_are_normal() -> None:
    result = aggregate_anomaly_results(
        threshold_result=ThresholdDetectionResult(anomaly_flag="normal"),
        zscore_result=ZScoreDetectionResult(
            z_score=1.0,
            threshold=3.0,
            anomaly_flag="normal",
            is_anomalous=False,
        ),
        three_sigma_result=ThreeSigmaDetectionResult(
            lower_bound=94.0,
            upper_bound=106.0,
            anomaly_flag="normal",
            is_anomalous=False,
        ),
    )

    assert result == AggregatedAnomalyResult(
        is_anomaly=False,
        severity="normal",
        reasons=[],
    )


def test_aggregate_anomaly_results_returns_not_evaluated_when_only_not_evaluated_exists() -> None:
    result = aggregate_anomaly_results(
        threshold_result=ThresholdDetectionResult(anomaly_flag="not_evaluated"),
    )

    assert result == AggregatedAnomalyResult(
        is_anomaly=False,
        severity="not_evaluated",
        reasons=[],
    )


def test_aggregate_anomaly_results_rejects_unknown_threshold_flag() -> None:
    try:
        aggregate_anomaly_results(
            threshold_result=ThresholdDetectionResult(anomaly_flag="invalid"),
        )
    except ValueError as exc:
        assert str(exc) == "Unsupported threshold anomaly_flag 'invalid'."
    else:
        raise AssertionError("Expected invalid threshold flag to raise ValueError.")


def test_aggregate_anomaly_results_rejects_unknown_statistical_flag() -> None:
    try:
        aggregate_anomaly_results(
            zscore_result=ZScoreDetectionResult(
                z_score=0.0,
                threshold=3.0,
                anomaly_flag="invalid",
                is_anomalous=False,
            ),
        )
    except ValueError as exc:
        assert str(exc) == "Unsupported zscore anomaly_flag 'invalid'."
    else:
        raise AssertionError("Expected invalid zscore flag to raise ValueError.")
