from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from rkaa.domain.impact_analyzer import ImpactAnalyzerService
from rkaa.domain.impact_manager.models import (
    EventCategory,
    ImpactEvent,
    ImpactSource,
    ImpactStatus,
)
from rkaa.infrastructure.config.kpi_threshold_loader import load_threshold_manager


def test_fr301_pipeline_uses_fr402_context_and_direction_config(tmp_path: Path) -> None:
    threshold_path = tmp_path / "thresholds.yaml"
    threshold_path.write_text(
        """
kpis:
  ENDC_SSR:
    direction_preference: higher_is_better
""".strip(),
        encoding="utf-8",
    )
    manager = load_threshold_manager(threshold_path)

    event = ImpactEvent(
        impact_id="IMP-301",
        ne_id="NE1",
        cell_id="CELL_A",
        t1_utc=datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc),
        t2_utc=datetime(2026, 8, 10, 11, 0, tzinfo=timezone.utc),
        impact_type="SOFTWARE_UPGRADE",
        description="integration",
        operator="tester",
        source=ImpactSource.MANUAL,
        status=ImpactStatus.CLOSED,
        created_at_utc=datetime(2026, 8, 1, tzinfo=timezone.utc),
        updated_at_utc=datetime(2026, 8, 1, tzinfo=timezone.utc),
        event_category=EventCategory.IMPACT,
    )
    data = pd.DataFrame(
        {
            "timestamp": [
                "2026-08-10T08:00:00Z",
                "2026-08-10T09:00:00Z",
                "2026-08-10T11:00:00Z",
                "2026-08-10T12:00:00Z",
            ],
            "ne_id": ["NE1"] * 4,
            "cell_id": ["CELL_A"] * 4,
            "kpi_name": ["ENDC_SSR"] * 4,
            "temporal_profile": ["BUSY"] * 4,
            "day_type": ["WEEKDAY"] * 4,
            "value": [98.2, 98.0, 94.0, 94.2],
        }
    )

    result = ImpactAnalyzerService().analyze(
        data,
        event,
        window_hours=2,
        direction_preferences=manager.direction_preferences(),
    )

    row = result.report_df.iloc[0]
    assert row["impact_id"] == "IMP-301"
    assert row["temporal_profile"] == "BUSY"
    assert row["day_type"] == "WEEKDAY"
    assert row["pre_count"] == 2
    assert row["post_count"] == 2
    assert row["trend_assessment"] == "DEGRADED"
