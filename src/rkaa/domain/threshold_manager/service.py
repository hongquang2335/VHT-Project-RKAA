"""Đánh giá thay đổi KPI theo ngưỡng cấu hình FR-303."""

from __future__ import annotations

import math

from rkaa.domain.threshold_manager.models import (
    DirectionThresholds,
    KpiThresholdPolicy,
    ThresholdDirection,
    ThresholdEvaluation,
    ThresholdLevel,
    ThresholdMode,
    ThresholdSeverity,
)


def _observed_magnitude(
    level: ThresholdLevel,
    *,
    delta_absolute: float,
    delta_percent: float,
) -> float | None:
    value = delta_absolute if level.mode is ThresholdMode.ABSOLUTE else delta_percent
    if not math.isfinite(value):
        return None
    return abs(float(value))


def _matches(
    level: ThresholdLevel | None,
    *,
    delta_absolute: float,
    delta_percent: float,
) -> tuple[bool, float | None]:
    if level is None:
        return False, None
    observed = _observed_magnitude(
        level,
        delta_absolute=delta_absolute,
        delta_percent=delta_percent,
    )
    return (observed is not None and observed >= level.value), observed


class ThresholdManagerService:
    """Tra cứu và áp dụng chính sách ngưỡng theo từng KPI."""

    def __init__(self, policies: dict[str, KpiThresholdPolicy]) -> None:
        self.policies = {str(key): value for key, value in policies.items()}

    def get_policy(self, kpi_name: str) -> KpiThresholdPolicy | None:
        return self.policies.get(str(kpi_name))

    def direction_preferences(self) -> dict[str, str]:
        """Trả ánh xạ chiều tốt để FR-301 diễn giải cải thiện/suy giảm."""

        return {
            kpi_name: policy.direction_preference.value
            for kpi_name, policy in self.policies.items()
        }

    def evaluate(
        self,
        kpi_name: str,
        *,
        delta_absolute: float,
        delta_percent: float,
    ) -> ThresholdEvaluation:
        policy = self.get_policy(kpi_name)
        if policy is None or not math.isfinite(delta_absolute) or math.isclose(
            delta_absolute, 0.0, abs_tol=1e-12
        ):
            return ThresholdEvaluation(severity=ThresholdSeverity.NONE)

        if delta_absolute > 0:
            direction = ThresholdDirection.INCREASE
            thresholds = policy.increase
        else:
            direction = ThresholdDirection.DECREASE
            thresholds = policy.decrease

        return self._evaluate_direction(
            direction,
            thresholds,
            delta_absolute=delta_absolute,
            delta_percent=delta_percent,
        )

    @staticmethod
    def _evaluate_direction(
        direction: ThresholdDirection,
        thresholds: DirectionThresholds,
        *,
        delta_absolute: float,
        delta_percent: float,
    ) -> ThresholdEvaluation:
        critical_match, critical_observed = _matches(
            thresholds.critical,
            delta_absolute=delta_absolute,
            delta_percent=delta_percent,
        )
        if critical_match and thresholds.critical is not None:
            return ThresholdEvaluation(
                severity=ThresholdSeverity.CRITICAL,
                direction=direction,
                matched_mode=thresholds.critical.mode,
                matched_threshold=thresholds.critical.value,
                observed_value=critical_observed,
            )

        warning_match, warning_observed = _matches(
            thresholds.warning,
            delta_absolute=delta_absolute,
            delta_percent=delta_percent,
        )
        if warning_match and thresholds.warning is not None:
            return ThresholdEvaluation(
                severity=ThresholdSeverity.WARNING,
                direction=direction,
                matched_mode=thresholds.warning.mode,
                matched_threshold=thresholds.warning.value,
                observed_value=warning_observed,
            )

        return ThresholdEvaluation(severity=ThresholdSeverity.NONE, direction=direction)
