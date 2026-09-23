from __future__ import annotations

from rkaa.domain.threshold_manager import (
    DirectionThreshold,
    KPIThresholdRule,
    ThresholdManager,
    ThresholdMode,
)


def test_fr303_evaluates_warning_and_critical_by_direction() -> None:
    manager = ThresholdManager(
        [
            KPIThresholdRule(
                kpi_name="CDR",
                direction_preference="lower_is_better",
                increase=DirectionThreshold(
                    mode=ThresholdMode.ABSOLUTE,
                    warning=1.0,
                    critical=3.0,
                ),
            )
        ]
    )

    warning = manager.evaluate("CDR", delta_abs=1.5, delta_percent=20.0)
    critical = manager.evaluate("CDR", delta_abs=3.5, delta_percent=40.0)

    assert warning["threshold_severity"] == "WARNING"
    assert warning["change_assessment"] == "degrading"
    assert critical["threshold_severity"] == "CRITICAL"


def test_fr303_supports_percent_thresholds() -> None:
    manager = ThresholdManager(
        [
            KPIThresholdRule(
                kpi_name="TRAFFIC",
                direction_preference="informational",
                decrease=DirectionThreshold(
                    mode=ThresholdMode.PERCENT,
                    warning=10.0,
                    critical=25.0,
                ),
            )
        ]
    )

    result = manager.evaluate("TRAFFIC", delta_abs=-5.0, delta_percent=-30.0)

    assert result["threshold_mode"] == "percent"
    assert result["threshold_value"] == 30.0
    assert result["threshold_severity"] == "CRITICAL"
