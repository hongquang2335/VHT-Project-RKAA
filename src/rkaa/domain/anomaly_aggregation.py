"""Aggregate anomaly detector results into one consistent decision."""

from __future__ import annotations

from dataclasses import dataclass

from rkaa.domain.three_sigma_detector import ThreeSigmaDetectionResult
from rkaa.domain.threshold_detector import ThresholdDetectionResult
from rkaa.domain.zscore_detector import ZScoreDetectionResult

_SEVERITY_ORDER = {
    "not_evaluated": 0,
    "normal": 1,
    "anomalous": 2,
    "warning": 3,
    "critical": 4,
}


@dataclass(frozen=True, slots=True)
class AggregatedAnomalyResult:
    """Unified anomaly decision built from multiple detector outputs."""

    is_anomaly: bool
    severity: str
    reasons: list[str]


def aggregate_anomaly_results(
    *,
    threshold_result: ThresholdDetectionResult | None = None,
    zscore_result: ZScoreDetectionResult | None = None,
    three_sigma_result: ThreeSigmaDetectionResult | None = None,
) -> AggregatedAnomalyResult:
    """Merge detector outputs into a single anomaly flag, severity, and reasons."""

    severities: list[str] = []
    reasons: list[str] = []

    if threshold_result is not None:
        threshold_flag = threshold_result.anomaly_flag
        if threshold_flag not in {"critical", "warning", "normal", "not_evaluated"}:
            raise ValueError(f"Unsupported threshold anomaly_flag '{threshold_flag}'.")
        severities.append(threshold_flag)
        if threshold_flag == "critical":
            reasons.append("threshold_critical")
        elif threshold_flag == "warning":
            reasons.append("threshold_warning")

    if zscore_result is not None:
        zscore_flag = zscore_result.anomaly_flag
        if zscore_flag not in {"anomalous", "normal"}:
            raise ValueError(f"Unsupported zscore anomaly_flag '{zscore_flag}'.")
        severities.append(zscore_flag)
        if zscore_flag == "anomalous":
            reasons.append("zscore_anomaly")

    if three_sigma_result is not None:
        three_sigma_flag = three_sigma_result.anomaly_flag
        if three_sigma_flag not in {"anomalous", "normal"}:
            raise ValueError(f"Unsupported three_sigma anomaly_flag '{three_sigma_flag}'.")
        severities.append(three_sigma_flag)
        if three_sigma_flag == "anomalous":
            reasons.append("three_sigma_anomaly")

    if not severities:
        return AggregatedAnomalyResult(
            is_anomaly=False,
            severity="not_evaluated",
            reasons=[],
        )

    severity = max(severities, key=_severity_rank)
    return AggregatedAnomalyResult(
        is_anomaly=severity in {"anomalous", "warning", "critical"},
        severity=severity,
        reasons=reasons,
    )


def _severity_rank(severity: str) -> int:
    try:
        return _SEVERITY_ORDER[severity]
    except KeyError as exc:
        raise ValueError(f"Unsupported severity '{severity}'.") from exc
