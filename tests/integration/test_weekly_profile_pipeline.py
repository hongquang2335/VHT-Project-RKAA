from __future__ import annotations

import pandas as pd

from rkaa.domain.baseline_engine import BaselineEngine
from rkaa.domain.temporal_analyzer import WeeklyCycleAnalyzer


def test_fr402_pipeline_separates_day_type_and_weekday_baselines() -> None:
    rows = []
    for date, day_type_value in (
        ("2026-08-03", 98.0),  # Monday
        ("2026-08-10", 100.0),  # Monday
        ("2026-08-15", 90.0),  # Saturday
        ("2026-08-16", 92.0),  # Sunday
    ):
        rows.append(
            {
                "timestamp": f"{date}T08:00:00+00:00",
                "period_end": f"{date}T08:15:00+00:00",
                "ne_id": "NE1",
                "cell_id": "CELL_A",
                "kpi_name": "ENDC_SSR",
                "value": day_type_value,
                "unit": "%",
                "temporal_profile": "BUSY",
                "profile_timezone": "UTC",
                "minute_of_day": 480,
                "time_of_day": "08:00",
            }
        )

    result = WeeklyCycleAnalyzer().analyze(pd.DataFrame(rows))
    engine = BaselineEngine()
    day_type = engine.compute_day_type(result.profiled_df)
    weekday = engine.compute_weekday(result.profiled_df, min_distinct_dates=2)

    assert set(result.profiled_df["day_type"]) == {"WEEKDAY", "WEEKEND"}
    assert set(day_type["day_type"]) == {"WEEKDAY", "WEEKEND"}
    assert weekday["day_of_week"].tolist() == ["MONDAY"]
    assert result.overlay_df.groupby("day_type")["sample_count"].sum().to_dict() == {
        "WEEKDAY": 2,
        "WEEKEND": 2,
    }
