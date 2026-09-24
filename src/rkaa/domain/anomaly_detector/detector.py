"""FR-302 anomaly decision logic for post-impact KPI values."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class ThresholdRule:
    """Configured FR-303 threshold consumed by FR-302.

    ``mode`` is ``absolute`` (compare the post mean) or ``delta_percent``.
    ``direction`` is ``above`` or ``below``.
    """

    direction: str
    mode: str
    value: float
    severity: str = "WARNING"

    def __post_init__(self) -> None:
        if self.direction not in {"above", "below"}:
            raise ValueError("threshold direction phải là 'above' hoặc 'below'")
        if self.mode not in {"absolute", "delta_percent"}:
            raise ValueError("threshold mode phải là 'absolute' hoặc 'delta_percent'")
        if not np.isfinite(float(self.value)):
            raise ValueError("threshold value phải hữu hạn")


@dataclass(frozen=True, slots=True)
class AnomalyDecision:
    sigma_applicable: bool
    reference_z_score: float
    anomaly_3sigma: bool
    threshold_configured: bool
    anomaly_threshold: bool
    threshold_severity: str
    anomaly_flag: bool
    anomaly_source: str
    anomaly_decision_source: str


class AnomalyDetector:
    """Detect FR-302 anomalies using reliable baseline and optional FR-303 threshold."""

    def __init__(self, *, sigma_threshold: float = 3.0) -> None:
        if sigma_threshold <= 0:
            raise ValueError("sigma_threshold phải > 0")
        self.sigma_threshold = float(sigma_threshold)

    @staticmethod
    def _threshold_breached(rule: ThresholdRule, *, post_mean: float, delta_percent: float) -> bool:
        observed = post_mean if rule.mode == "absolute" else delta_percent
        if not np.isfinite(observed):
            return False
        return observed > rule.value if rule.direction == "above" else observed < rule.value

    def detect(
        self,
        *,
        post_mean: float,
        baseline_mean: float,
        baseline_std: float,
        baseline_reliable: bool,
        comparison_eligible: bool,
        delta_percent: float = np.nan,
        threshold_rule: ThresholdRule | None = None,
    ) -> AnomalyDecision:
        sigma_applicable = bool(
            comparison_eligible
            and baseline_reliable
            and np.isfinite(baseline_mean)
            and np.isfinite(baseline_std)
            and float(baseline_std) > 0
            and np.isfinite(post_mean)
        )
        z_score = (
            (float(post_mean) - float(baseline_mean)) / float(baseline_std)
            if sigma_applicable
            else np.nan
        )
        anomaly_3sigma = bool(sigma_applicable and abs(z_score) >= self.sigma_threshold)

        threshold_configured = threshold_rule is not None
        anomaly_threshold = bool(
            comparison_eligible
            and threshold_rule is not None
            and self._threshold_breached(
                threshold_rule,
                post_mean=float(post_mean),
                delta_percent=float(delta_percent),
            )
        )

        # Existing project policy: an explicitly configured KPI threshold is the
        # decision authority; 3-sigma remains diagnostic. Without a configured
        # threshold FR-302 falls back to 3-sigma.
        if not comparison_eligible:
            anomaly_flag = False
            decision_source = "INELIGIBLE_DATA"
        elif threshold_rule is not None:
            anomaly_flag = anomaly_threshold
            decision_source = "FR303_THRESHOLD"
        else:
            anomaly_flag = anomaly_3sigma
            decision_source = "FR302_3SIGMA"

        if anomaly_threshold:
            source = "THRESHOLD"
        elif anomaly_3sigma:
            source = "3SIGMA"
        else:
            source = "NONE"

        return AnomalyDecision(
            sigma_applicable=sigma_applicable,
            reference_z_score=float(z_score),
            anomaly_3sigma=anomaly_3sigma,
            threshold_configured=threshold_configured,
            anomaly_threshold=anomaly_threshold,
            threshold_severity=threshold_rule.severity if threshold_rule else "NORMAL",
            anomaly_flag=anomaly_flag,
            anomaly_source=source,
            anomaly_decision_source=decision_source,
        )
