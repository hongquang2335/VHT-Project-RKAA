from __future__ import annotations

import math

import pandas as pd

from rkaa.domain.statistical_engine import StatisticalEngine


def test_compare_groups_computes_descriptive_delta_and_p_values() -> None:
    pre = pd.DataFrame(
        {
            "ne_id": ["NE1"] * 5,
            "cell_id": ["C1"] * 5,
            "kpi_name": ["ENDC_SSR"] * 5,
            "temporal_profile": ["BUSY"] * 5,
            "day_type": ["WEEKDAY"] * 5,
            "value": [98.0, 98.1, 97.9, 98.2, 97.8],
        }
    )
    post = pre.copy()
    post["value"] = [94.0, 94.2, 93.8, 94.1, 93.9]

    result = StatisticalEngine().compare_groups(
        pre,
        post,
        group_keys=["ne_id", "cell_id", "kpi_name", "temporal_profile", "day_type"],
    )

    assert len(result) == 1
    assert result["pre_count"].item() == 5
    assert result["post_count"].item() == 5
    assert result["delta_mean"].item() < 0
    assert result["change_direction"].item() == "DECREASE"
    assert math.isfinite(result["t_test_p_value"].item())
    assert math.isfinite(result["mann_whitney_p_value"].item())
    assert bool(result["statistically_significant"].item()) is True


def test_compare_groups_only_returns_context_present_in_both_windows() -> None:
    pre = pd.DataFrame(
        {
            "kpi_name": ["K1", "K2"],
            "value": [1.0, 2.0],
        }
    )
    post = pd.DataFrame(
        {
            "kpi_name": ["K1", "K3"],
            "value": [1.5, 3.0],
        }
    )

    result = StatisticalEngine().compare_groups(pre, post, group_keys=["kpi_name"])

    assert result["kpi_name"].tolist() == ["K1"]
