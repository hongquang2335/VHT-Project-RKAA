from __future__ import annotations

import pandas as pd

from rkaa.domain.anomaly_detector import AnomalyDetectionService
from rkaa.domain.threshold_manager import (
    DirectionThresholds,
    KpiThresholdPolicy,
    ThresholdLevel,
    ThresholdManagerService,
    ThresholdMode,
)


def _impact(post_mean: float, delta_mean: float, delta_percent: float) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ne_id": "NE1",
                "cell_id": "C1",
                "kpi_name": "ENDC_SSR",
                "temporal_profile": "BUSY",
                "day_type": "WEEKDAY",
                "post_mean": post_mean,
                "delta_mean": delta_mean,
                "delta_percent": delta_percent,
            }
        ]
    )


def _baseline() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ne_id": "NE1",
                "cell_id": "C1",
                "kpi_name": "ENDC_SSR",
                "temporal_profile": "BUSY",
                "day_type": "WEEKDAY",
                "sample_count": 100,
                "mean": 100.0,
                "std": 2.0,
                "p05": 96.7,
                "p95": 103.3,
            }
        ]
    )


def _manager() -> ThresholdManagerService:
    return ThresholdManagerService(
        {
            "ENDC_SSR": KpiThresholdPolicy(
                kpi_name="ENDC_SSR",
                decrease=DirectionThresholds(
                    warning=ThresholdLevel(ThresholdMode.PERCENTAGE, 2.0),
                    critical=ThresholdLevel(ThresholdMode.PERCENTAGE, 5.0),
                ),
            )
        }
    )


def test_two_sigma_baseline_detects_2_5_sigma_without_three_sigma() -> None:
    result = AnomalyDetectionService(_manager()).detect(
        _impact(post_mean=95.0, delta_mean=-5.0, delta_percent=-5.0),
        _baseline(),
    )

    assert bool(result["baseline_abnormal"].item()) is True
    assert bool(result["three_sigma_abnormal"].item()) is False
    assert bool(result["anomaly_flag"].item()) is True


def test_three_sigma_or_critical_threshold_produces_critical_severity() -> None:
    result = AnomalyDetectionService(_manager()).detect(
        _impact(post_mean=93.0, delta_mean=-7.0, delta_percent=-7.0),
        _baseline(),
    )

    assert bool(result["three_sigma_abnormal"].item()) is True
    assert result["threshold_severity"].item() == "CRITICAL"
    assert result["anomaly_severity"].item() == "CRITICAL"
    assert "THREE_SIGMA" in result["anomaly_methods"].item()


def test_baseline_is_joined_by_day_type_not_crossed() -> None:
    baseline = _baseline()
    baseline.loc[0, "day_type"] = "WEEKEND"

    result = AnomalyDetectionService(_manager()).detect(
        _impact(post_mean=90.0, delta_mean=-10.0, delta_percent=-10.0),
        baseline,
    )

    assert pd.isna(result["historical_z_score"].item())
    assert bool(result["baseline_abnormal"].item()) is False
