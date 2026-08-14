from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from rkaa.domain.impact_analyzer import ImpactAnalyzerService
from rkaa.domain.impact_manager.models import (
    EventCategory,
    ImpactEvent,
    ImpactSource,
    ImpactStatus,
)


def _event() -> ImpactEvent:
    return ImpactEvent(
        impact_id="IMP-1",
        ne_id="NE1",
        cell_id="CELL_A",
        t1_utc=datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc),
        t2_utc=datetime(2026, 8, 10, 11, 0, tzinfo=timezone.utc),
        impact_type="SOFTWARE_UPGRADE",
        description="test",
        operator="tester",
        source=ImpactSource.MANUAL,
        status=ImpactStatus.CLOSED,
        created_at_utc=datetime(2026, 8, 1, tzinfo=timezone.utc),
        updated_at_utc=datetime(2026, 8, 1, tzinfo=timezone.utc),
        event_category=EventCategory.IMPACT,
    )


def _row(ts: str, value: float, *, cell: str = "CELL_A", day_type: str = "WEEKDAY") -> dict:
    return {
        "timestamp": ts,
        "ne_id": "NE1",
        "cell_id": cell,
        "kpi_name": "ENDC_SSR",
        "temporal_profile": "BUSY",
        "day_type": day_type,
        "value": value,
    }


def test_analyzer_filters_event_cell_and_builds_pre_post_windows() -> None:
    rows = [
        _row("2026-08-10T08:00:00Z", 98.2),
        _row("2026-08-10T09:00:00Z", 98.0),
        _row("2026-08-10T10:00:00Z", 50.0),
        _row("2026-08-10T11:00:00Z", 94.0),
        _row("2026-08-10T12:00:00Z", 94.2),
        _row("2026-08-10T09:00:00Z", 10.0, cell="CELL_B"),
        _row("2026-08-10T12:00:00Z", 10.0, cell="CELL_B"),
    ]

    result = ImpactAnalyzerService().analyze(
        pd.DataFrame(rows),
        _event(),
        window_hours=2,
        direction_preferences={"ENDC_SSR": "higher_is_better"},
    )

    assert set(result.pre_df["cell_id"]) == {"CELL_A"}
    assert set(result.post_df["cell_id"]) == {"CELL_A"}
    assert "2026-08-10 10:00:00+00:00" not in result.pre_df["timestamp"].astype(str).tolist()
    assert result.report_df["delta_mean"].item() < 0
    assert result.report_df["trend_assessment"].item() == "DEGRADED"


def test_analyzer_never_pairs_weekday_pre_with_weekend_post() -> None:
    rows = [
        _row("2026-08-10T09:00:00Z", 98.0, day_type="WEEKDAY"),
        _row("2026-08-10T11:00:00Z", 90.0, day_type="WEEKEND"),
    ]

    result = ImpactAnalyzerService().analyze(pd.DataFrame(rows), _event(), window_hours=2)

    assert result.report_df.empty
