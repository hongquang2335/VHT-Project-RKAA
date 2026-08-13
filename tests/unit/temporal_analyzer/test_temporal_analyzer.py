from __future__ import annotations

import pandas as pd

from rkaa.domain.temporal_analyzer.models import (
    ProfileWindow,
    TemporalProfile,
    TemporalProfileConfig,
)
from rkaa.domain.temporal_analyzer.service import TemporalAnalyzer


def _config() -> TemporalProfileConfig:
    return TemporalProfileConfig(
        timezone="UTC",
        windows=(
            ProfileWindow(TemporalProfile.BUSY, 7 * 60, 21 * 60),
            ProfileWindow(TemporalProfile.TRANSITION, 6 * 60, 7 * 60),
            ProfileWindow(TemporalProfile.TRANSITION, 21 * 60, 22 * 60),
            ProfileWindow(TemporalProfile.OFF_PEAK, 22 * 60, 6 * 60),
        ),
    )


def test_classifies_busy_off_peak_and_transition_boundaries() -> None:
    analyzer = TemporalAnalyzer(_config())

    assert analyzer.classify_period(5 * 60 + 59) == "OFF_PEAK"
    assert analyzer.classify_period(6 * 60) == "TRANSITION"
    assert analyzer.classify_period(6 * 60 + 59) == "TRANSITION"
    assert analyzer.classify_period(7 * 60) == "BUSY"
    assert analyzer.classify_period(20 * 60 + 59) == "BUSY"
    assert analyzer.classify_period(21 * 60) == "TRANSITION"
    assert analyzer.classify_period(21 * 60 + 59) == "TRANSITION"
    assert analyzer.classify_period(22 * 60) == "OFF_PEAK"


def test_analyze_preserves_ne_cell_and_builds_overlay_profile() -> None:
    df = pd.DataFrame(
        {
            "timestamp": [
                "2026-08-10T05:00:00+00:00",
                "2026-08-10T06:15:00+00:00",
                "2026-08-10T08:00:00+00:00",
            ],
            "period_end": [
                "2026-08-10T05:15:00+00:00",
                "2026-08-10T06:30:00+00:00",
                "2026-08-10T08:15:00+00:00",
            ],
            "ne_id": ["NE1"] * 3,
            "cell_id": ["CELL_A"] * 3,
            "kpi_name": ["ENDC_SSR"] * 3,
            "value": [98.0, 97.0, 99.0],
            "unit": ["%"] * 3,
        }
    )

    result = TemporalAnalyzer(_config()).analyze(df)

    assert result.profiled_df["temporal_profile"].tolist() == [
        "OFF_PEAK",
        "TRANSITION",
        "BUSY",
    ]
    assert result.profiled_df["cell_id"].tolist() == ["CELL_A"] * 3
    assert set(result.overlay_df["temporal_profile"]) == {
        "BUSY",
        "OFF_PEAK",
        "TRANSITION",
    }
