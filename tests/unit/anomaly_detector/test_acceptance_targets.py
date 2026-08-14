from __future__ import annotations

import numpy as np
import pandas as pd

from rkaa.domain.anomaly_detector import AnomalyDetectionService
from rkaa.domain.threshold_manager import ThresholdManagerService


def _baseline() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ne_id": "NE1",
                "cell_id": "C1",
                "kpi_name": "K1",
                "temporal_profile": "BUSY",
                "day_type": "WEEKDAY",
                "sample_count": 1000,
                "mean": 0.0,
                "std": 1.0,
            }
        ]
    )


def _report(post_values: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ne_id": "NE1",
            "cell_id": "C1",
            "kpi_name": "K1",
            "temporal_profile": "BUSY",
            "day_type": "WEEKDAY",
            "post_mean": post_values,
            "delta_mean": post_values,
            "delta_percent": np.nan,
        }
    )


def test_controlled_two_sigma_cases_meet_detection_target() -> None:
    magnitudes = np.linspace(2.0, 5.0, 1000)
    signs = np.where(np.arange(len(magnitudes)) % 2 == 0, 1.0, -1.0)
    report = _report(magnitudes * signs)

    result = AnomalyDetectionService(ThresholdManagerService({})).detect(report, _baseline())

    detection_rate = float(result["anomaly_flag"].mean())
    assert detection_rate >= 0.90


def test_controlled_normal_gaussian_false_alarm_target() -> None:
    rng = np.random.default_rng(20260814)
    report = _report(rng.normal(0.0, 1.0, 20_000))

    result = AnomalyDetectionService(ThresholdManagerService({})).detect(report, _baseline())

    false_alarm_rate = float(result["anomaly_flag"].mean())
    assert false_alarm_rate <= 0.05
