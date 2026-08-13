from __future__ import annotations

import pandas as pd

from rkaa.domain.baseline_engine import BaselineEngine


def _profiled() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ne_id": ["NE1"] * 6,
            "cell_id": ["CELL_A"] * 6,
            "kpi_name": ["ENDC_SSR"] * 6,
            "temporal_profile": ["BUSY"] * 6,
            "day_type": ["WEEKDAY"] * 4 + ["WEEKEND"] * 2,
            "day_of_week": ["MONDAY", "MONDAY", "MONDAY", "TUESDAY", "SATURDAY", "SUNDAY"],
            "calendar_date": [
                "2026-08-03",
                "2026-08-10",
                "2026-08-10",
                "2026-08-11",
                "2026-08-15",
                "2026-08-16",
            ],
            "value": [98.0, 100.0, 99.0, 97.0, 90.0, 92.0],
            "unit": ["%"] * 6,
        }
    )


def test_compute_day_type_creates_separate_weekday_weekend_baselines() -> None:
    baseline = BaselineEngine().compute_day_type(_profiled())

    assert set(baseline["day_type"]) == {"WEEKDAY", "WEEKEND"}
    means = baseline.set_index("day_type")["mean"].to_dict()
    assert means["WEEKDAY"] == 98.5
    assert means["WEEKEND"] == 91.0


def test_compute_weekday_emits_only_days_with_enough_distinct_dates() -> None:
    baseline = BaselineEngine().compute_weekday(_profiled(), min_distinct_dates=2)

    assert baseline["day_of_week"].tolist() == ["MONDAY"]
    assert baseline["distinct_date_count"].item() == 2
    assert baseline["sample_count"].item() == 3


def test_compare_same_day_type_never_pairs_weekday_with_weekend() -> None:
    pre = pd.DataFrame(
        {
            "ne_id": ["NE1", "NE1"],
            "cell_id": ["CELL_A", "CELL_A"],
            "kpi_name": ["ENDC_SSR", "ENDC_SSR"],
            "temporal_profile": ["BUSY", "BUSY"],
            "day_type": ["WEEKDAY", "WEEKEND"],
            "value": [98.0, 90.0],
        }
    )
    post = pd.DataFrame(
        {
            "ne_id": ["NE1", "NE1"],
            "cell_id": ["CELL_A", "CELL_A"],
            "kpi_name": ["ENDC_SSR", "ENDC_SSR"],
            "temporal_profile": ["BUSY", "BUSY"],
            "day_type": ["WEEKDAY", "WEEKDAY"],
            "value": [99.0, 100.0],
        }
    )

    compared = BaselineEngine().compare_same_day_type_windows(pre, post)

    assert compared["day_type"].tolist() == ["WEEKDAY"]
    assert compared["pre_count"].item() == 1
    assert compared["post_count"].item() == 2
