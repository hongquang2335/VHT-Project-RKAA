from datetime import datetime, timezone

import pandas as pd

from rkaa.domain.noise_filter.impact_window_filter import ImpactWindowFilter
from rkaa.domain.noise_filter.models import ExclusionWindow, ImpactWindowConfig


def test_impact_window_excludes_matching_station_prefix_inside_half_open_window() -> None:
    df = pd.DataFrame(
        {
            "timestamp": [
                "2026-07-01 00:00:00",
                "2026-07-01 00:15:00",
                "2026-07-01 00:30:00",
                "2026-07-01 00:15:00",
            ],
            "ne_id": ["gHM00001_30", "gHM00001_30", "gHM00001_30", "gHM00002_30"],
            "kpi_name": ["ENDC_SSR"] * 4,
            "value": [99.0, 50.0, 98.0, 97.0],
        }
    )
    window = ExclusionWindow(
        ne_id="gHM00001",
        t1_utc=datetime(2026, 7, 1, 0, 15, tzinfo=timezone.utc),
        t2_utc=datetime(2026, 7, 1, 0, 30, tzinfo=timezone.utc),
        reason="SOFTWARE_UPGRADE",
        source="FR103:test",
    )
    rule = ImpactWindowFilter(
        ImpactWindowConfig(
            enabled=True,
            excluded_impact_types=("SOFTWARE_UPGRADE",),
            match_mode="exact_or_prefix",
        ),
        [window],
    )

    result = rule.apply(df)

    assert len(result.excluded_df) == 1
    assert result.excluded_df.iloc[0]["filter_reason"] == "SOFTWARE_UPGRADE"
    assert len(result.cleaned_df) == 3
