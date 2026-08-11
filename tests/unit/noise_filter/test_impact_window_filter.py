from datetime import datetime, timezone

import pandas as pd

from rkaa.domain.noise_filter.impact_window_filter import ImpactWindowFilter
from rkaa.domain.noise_filter.models import ExclusionWindow, ImpactWindowConfig


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": [
                "2026-07-01 00:00:00",
                "2026-07-01 00:15:00",
                "2026-07-01 00:15:00",
                "2026-07-01 00:15:00",
            ],
            "period_end": [
                "2026-07-01 00:15:00",
                "2026-07-01 00:30:00",
                "2026-07-01 00:30:00",
                "2026-07-01 00:30:00",
            ],
            "ne_id": ["gHM00001", "gHM00001", "gHM00001", "gHM00002"],
            "cell_id": ["CELL_A", "CELL_A", "CELL_B", "CELL_A"],
            "kpi_name": ["ENDC_SSR"] * 4,
            "value": [99.0, 50.0, 60.0, 97.0],
        }
    )


def test_cell_scoped_window_excludes_only_matching_ne_and_cell() -> None:
    window = ExclusionWindow(
        ne_id="gHM00001",
        cell_id="CELL_A",
        t1_utc=datetime(2026, 7, 1, 0, 15, tzinfo=timezone.utc),
        t2_utc=datetime(2026, 7, 1, 0, 30, tzinfo=timezone.utc),
        reason="SOFTWARE_UPGRADE",
        source="FR202:test",
    )
    rule = ImpactWindowFilter(
        ImpactWindowConfig(
            enabled=True,
            excluded_impact_types=("SOFTWARE_UPGRADE",),
            match_mode="exact",
        ),
        [window],
    )

    result = rule.apply(_df())

    assert len(result.excluded_df) == 1
    assert result.excluded_df.iloc[0]["cell_id"] == "CELL_A"
    assert result.excluded_df.iloc[0]["filter_reason"] == "SOFTWARE_UPGRADE"


def test_ne_scoped_window_with_no_cell_excludes_all_cells_of_ne() -> None:
    window = ExclusionWindow(
        ne_id="gHM00001",
        cell_id=None,
        t1_utc=datetime(2026, 7, 1, 0, 15, tzinfo=timezone.utc),
        t2_utc=datetime(2026, 7, 1, 0, 30, tzinfo=timezone.utc),
        reason="SOFTWARE_UPGRADE",
        source="FR202:test",
    )
    result = ImpactWindowFilter(ImpactWindowConfig(match_mode="exact"), [window]).apply(_df())

    assert len(result.excluded_df) == 2
    assert set(result.excluded_df["cell_id"]) == {"CELL_A", "CELL_B"}
