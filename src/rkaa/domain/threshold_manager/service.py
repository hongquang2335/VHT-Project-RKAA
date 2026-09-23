"""FR-303: đánh giá KPI delta theo warning/critical threshold cấu hình YAML."""

from __future__ import annotations

from collections.abc import Iterable

import math

from rkaa.domain.threshold_manager.models import (
    KPIThresholdRule,
    ThresholdMode,
    ThresholdSeverity,
)


class ThresholdManager:
    """Kho rule FR-303 và logic đánh giá thay đổi KPI."""

    def __init__(self, rules: Iterable[KPIThresholdRule]) -> None:
        self._rules = {rule.kpi_name: rule for rule in rules}

    @property
    def rules(self) -> dict[str, KPIThresholdRule]:
        return dict(self._rules)

    def get(self, kpi_name: str) -> KPIThresholdRule | None:
        return self._rules.get(str(kpi_name))

    def direction_preference(self, kpi_name: str) -> str:
        rule = self.get(kpi_name)
        return rule.direction_preference if rule else "informational"

    def evaluate(
        self,
        kpi_name: str,
        *,
        delta_abs: float,
        delta_percent: float | None,
    ) -> dict[str, object]:
        """Đánh giá severity của một thay đổi KPI.

        ``delta_abs`` là current - reference theo đơn vị gốc. ``delta_percent`` là
        % thay đổi so với reference mean. Threshold được chọn theo chiều tăng/giảm
        và mode absolute/percent của YAML.
        """

        rule = self.get(kpi_name)
        if rule is None or not rule.enabled or not math.isfinite(float(delta_abs)):
            return {
                "threshold_configured": False,
                "threshold_direction": "none",
                "threshold_mode": "none",
                "threshold_value": math.nan,
                "threshold_severity": ThresholdSeverity.NORMAL.value,
                "change_assessment": self._assessment(
                    rule.direction_preference if rule else "informational",
                    delta_abs,
                ),
            }

        if delta_abs > 0:
            direction = "increase"
            threshold = rule.increase
        elif delta_abs < 0:
            direction = "decrease"
            threshold = rule.decrease
        else:
            direction = "none"
            threshold = None

        if threshold is None:
            value = 0.0
            configured = False
            mode = "none"
            warning = critical = None
        else:
            mode = threshold.mode.value
            if threshold.mode is ThresholdMode.ABSOLUTE:
                value = abs(float(delta_abs))
            else:
                value = abs(float(delta_percent)) if delta_percent is not None else math.nan
            warning = threshold.warning
            critical = threshold.critical
            configured = warning is not None or critical is not None

        severity = ThresholdSeverity.NORMAL
        if configured and math.isfinite(value):
            if critical is not None and value >= critical:
                severity = ThresholdSeverity.CRITICAL
            elif warning is not None and value >= warning:
                severity = ThresholdSeverity.WARNING

        return {
            "threshold_configured": configured,
            "threshold_direction": direction,
            "threshold_mode": mode,
            "threshold_value": value,
            "threshold_severity": severity.value,
            "change_assessment": self._assessment(rule.direction_preference, delta_abs),
        }

    @staticmethod
    def _assessment(direction_preference: str, delta_abs: float) -> str:
        if abs(float(delta_abs)) <= 1e-12:
            return "stable"
        if direction_preference == "higher_is_better":
            return "improving" if delta_abs > 0 else "degrading"
        if direction_preference == "lower_is_better":
            return "improving" if delta_abs < 0 else "degrading"
        return "increasing" if delta_abs > 0 else "decreasing"
