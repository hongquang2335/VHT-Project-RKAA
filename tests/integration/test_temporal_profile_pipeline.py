from __future__ import annotations

from pathlib import Path

import pandas as pd

from rkaa.domain.baseline_engine import BaselineEngine
from rkaa.domain.temporal_analyzer import TemporalAnalyzer
from rkaa.infrastructure.config.temporal_profile_loader import load_temporal_profile_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_fr401_pipeline_produces_three_separate_profile_baselines() -> None:
    rows = []
    for day in (10, 11):
        for hour, value in ((5, 90.0), (6, 95.0), (8, 99.0)):
            rows.append(
                {
                    "timestamp": f"2026-08-{day:02d}T{hour:02d}:00:00+00:00",
                    "period_end": f"2026-08-{day:02d}T{hour:02d}:05:00+00:00",
                    "ne_id": "NE1",
                    "cell_id": "CELL_A",
                    "kpi_name": "ENDC_SSR",
                    "value": value,
                    "unit": "%",
                }
            )
    df = pd.DataFrame(rows)

    config = load_temporal_profile_config(
        PROJECT_ROOT / "configs" / "temporal_profile.yaml"
    )
    temporal = TemporalAnalyzer(config).analyze(df)
    baseline = BaselineEngine().compute(temporal.profiled_df)

    assert set(temporal.profiled_df["temporal_profile"]) == {
        "BUSY",
        "OFF_PEAK",
        "TRANSITION",
    }
    assert len(baseline) == 3
    assert baseline.groupby("temporal_profile")["sample_count"].sum().to_dict() == {
        "BUSY": 2,
        "OFF_PEAK": 2,
        "TRANSITION": 2,
    }
