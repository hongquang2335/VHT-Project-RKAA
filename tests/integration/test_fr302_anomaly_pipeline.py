from __future__ import annotations

from pathlib import Path

import pandas as pd

from rkaa.domain.anomaly_detector import AnomalyDetectionService
from rkaa.infrastructure.config.kpi_threshold_loader import load_threshold_manager


def test_fr302_combines_baseline_sigma_and_configured_threshold(tmp_path: Path) -> None:
    threshold_path = tmp_path / "thresholds.yaml"
    threshold_path.write_text(
        """
kpis:
  ENDC_SSR:
    direction_preference: higher_is_better
    decrease:
      warning: {type: PERCENTAGE, value: 2}
      critical: {type: PERCENTAGE, value: 5}
""".strip(),
        encoding="utf-8",
    )
    impact_report = pd.DataFrame(
        [
            {
                "impact_id": "IMP-302",
                "ne_id": "NE1",
                "cell_id": "CELL_A",
                "kpi_name": "ENDC_SSR",
                "temporal_profile": "BUSY",
                "day_type": "WEEKDAY",
                "post_mean": 93.0,
                "delta_mean": -7.0,
                "delta_percent": -7.0,
            }
        ]
    )
    baseline = pd.DataFrame(
        [
            {
                "ne_id": "NE1",
                "cell_id": "CELL_A",
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

    result = AnomalyDetectionService(load_threshold_manager(threshold_path)).detect(
        impact_report,
        baseline,
    )

    row = result.iloc[0]
    assert bool(row["baseline_abnormal"]) is True
    assert bool(row["three_sigma_abnormal"]) is True
    assert row["threshold_severity"] == "CRITICAL"
    assert row["anomaly_severity"] == "CRITICAL"
    assert set(row["anomaly_methods"].split("|")) == {
        "HISTORICAL_BASELINE_2SIGMA",
        "THREE_SIGMA",
        "CONFIGURED_THRESHOLD",
    }
