from __future__ import annotations

from pathlib import Path

import pandas as pd

from rkaa.infrastructure.visualization.trend_png import (
    FIGURE_SIZE_INCHES,
    write_trend_png,
)


def test_fr403_png_writer_and_half_size_canvas(tmp_path: Path) -> None:
    components = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=4, freq="h", tz="UTC"),
            "ne_id": ["NE1"] * 4,
            "cell_id": ["CELL1"] * 4,
            "kpi_name": ["KPI1"] * 4,
            "value": [90.0, 91.0, 92.0, 93.0],
            "trend": [90.2, 90.9, 91.8, 92.7],
        }
    )
    summary = pd.DataFrame(
        [
            {
                "ne_id": "NE1",
                "cell_id": "CELL1",
                "kpi_name": "KPI1",
                "trend_label": "improving",
                "r2": 0.91,
                "trend_slope_per_day": 0.4,
            }
        ]
    )

    output = write_trend_png(
        components,
        summary,
        ne_id="NE1",
        cell_id="CELL1",
        kpi_name="KPI1",
        output_path=tmp_path / "trend.svg",
    )

    assert FIGURE_SIZE_INCHES == (6.0, 2.6)
    assert output.name == "trend.png"
    assert output.exists()
    assert output.stat().st_size > 100
    assert output.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
