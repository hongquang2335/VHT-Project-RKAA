from __future__ import annotations

import math

from rkaa.domain.anomaly_detector import AnomalyDetector, ThresholdRule


def test_fr302_3sigma_fallback_and_zero_variance_fail_closed() -> None:
    detector = AnomalyDetector(sigma_threshold=3.0)

    anomalous = detector.detect(
        post_mean=130.0,
        baseline_mean=100.0,
        baseline_std=5.0,
        baseline_reliable=True,
        comparison_eligible=True,
    )
    assert anomalous.sigma_applicable
    assert anomalous.reference_z_score == 6.0
    assert anomalous.anomaly_3sigma
    assert anomalous.anomaly_flag
    assert anomalous.anomaly_decision_source == "FR302_3SIGMA"

    zero_std = detector.detect(
        post_mean=130.0,
        baseline_mean=100.0,
        baseline_std=0.0,
        baseline_reliable=True,
        comparison_eligible=True,
    )
    assert not zero_std.sigma_applicable
    assert math.isnan(zero_std.reference_z_score)
    assert not zero_std.anomaly_3sigma
    assert not zero_std.anomaly_flag


def test_configured_threshold_is_decision_authority_but_completeness_still_gates() -> None:
    detector = AnomalyDetector()
    rule = ThresholdRule(direction="above", mode="absolute", value=120.0, severity="CRITICAL")

    decision = detector.detect(
        post_mean=125.0,
        baseline_mean=100.0,
        baseline_std=20.0,
        baseline_reliable=True,
        comparison_eligible=True,
        threshold_rule=rule,
    )
    assert decision.anomaly_threshold
    assert decision.anomaly_flag
    assert decision.anomaly_decision_source == "FR303_THRESHOLD"

    ineligible = detector.detect(
        post_mean=125.0,
        baseline_mean=100.0,
        baseline_std=20.0,
        baseline_reliable=True,
        comparison_eligible=False,
        threshold_rule=rule,
    )
    assert not ineligible.anomaly_flag
    assert ineligible.anomaly_decision_source == "INELIGIBLE_DATA"
