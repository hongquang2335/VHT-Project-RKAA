from __future__ import annotations

import pandas as pd

from rkaa.domain.trend_analyzer import ValidNECellSelector


def test_valid_pair_requires_days_and_completeness_without_case_tuning() -> None:
    good = pd.date_range("2026-01-01", periods=24 * 15, freq="h", tz="UTC")
    sparse = good[::2]
    frame = pd.DataFrame(
        {
            "timestamp": [*good, *sparse],
            "ne_id": ["NE1"] * len(good) + ["NE2"] * len(sparse),
            "cell_id": ["C1"] * len(good) + ["C2"] * len(sparse),
        }
    )

    result = ValidNECellSelector(
        granularity_minutes=60,
        minimum_clean_days=14,
        minimum_completeness=0.70,
    ).evaluate(frame)

    by_ne = result.set_index("ne_id")
    assert bool(by_ne.loc["NE1", "is_valid_pair"]) is True
    assert bool(by_ne.loc["NE2", "is_valid_pair"]) is False
    assert "LOW_COMPLETENESS" in by_ne.loc["NE2", "invalid_reason"]


def test_pair_with_timestamps_but_no_usable_kpi_values_is_invalid() -> None:
    timestamps = pd.date_range("2026-01-01", periods=24 * 15, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "ne_id": "NE_NULL",
            "cell_id": "CELL_NULL",
            "value": float("nan"),
        }
    )
    result = ValidNECellSelector(
        granularity_minutes=60,
        minimum_clean_days=14,
        minimum_completeness=0.70,
    ).evaluate(frame)
    row = result.iloc[0]
    assert bool(row["is_valid_pair"]) is False
    assert row["usable_value_count"] == 0
    assert "NO_USABLE_KPI_VALUES" in row["invalid_reason"]
