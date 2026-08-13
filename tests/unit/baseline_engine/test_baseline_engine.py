from __future__ import annotations

import pandas as pd

from rkaa.domain.baseline_engine.service import BaselineEngine


def _profiled() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ne_id": ["NE1"] * 6,
            "cell_id": ["CELL_A"] * 6,
            "kpi_name": ["ENDC_SSR"] * 6,
            "temporal_profile": [
                "OFF_PEAK",
                "OFF_PEAK",
                "TRANSITION",
                "TRANSITION",
                "BUSY",
                "BUSY",
            ],
            "value": [90.0, 92.0, 94.0, 96.0, 98.0, 100.0],
            "unit": ["%"] * 6,
        }
    )


def test_compute_creates_separate_baseline_for_three_profiles() -> None:
    baseline = BaselineEngine().compute(_profiled())

    assert len(baseline) == 3
    assert set(baseline["temporal_profile"]) == {"BUSY", "OFF_PEAK", "TRANSITION"}
    means = baseline.set_index("temporal_profile")["mean"].to_dict()
    assert means["OFF_PEAK"] == 91.0
    assert means["TRANSITION"] == 95.0
    assert means["BUSY"] == 99.0


def test_attach_baseline_never_matches_a_different_temporal_profile() -> None:
    profiled = _profiled().iloc[[0, 4]].copy()
    baseline = BaselineEngine().compute(_profiled())

    attached = BaselineEngine().attach_baseline(profiled, baseline)

    assert attached.loc[attached["temporal_profile"] == "OFF_PEAK", "baseline_mean"].item() == 91.0
    assert attached.loc[attached["temporal_profile"] == "BUSY", "baseline_mean"].item() == 99.0


def test_compare_pre_post_only_pairs_same_profile() -> None:
    pre = pd.DataFrame(
        {
            "ne_id": ["NE1", "NE1"],
            "cell_id": ["CELL_A", "CELL_A"],
            "kpi_name": ["ENDC_SSR", "ENDC_SSR"],
            "temporal_profile": ["BUSY", "OFF_PEAK"],
            "value": [98.0, 90.0],
        }
    )
    post = pd.DataFrame(
        {
            "ne_id": ["NE1", "NE1"],
            "cell_id": ["CELL_A", "CELL_A"],
            "kpi_name": ["ENDC_SSR", "ENDC_SSR"],
            "temporal_profile": ["BUSY", "TRANSITION"],
            "value": [99.0, 95.0],
        }
    )

    compared = BaselineEngine().compare_same_profile_windows(pre, post)

    assert compared["temporal_profile"].tolist() == ["BUSY"]
    assert compared["delta_mean"].item() == 1.0
