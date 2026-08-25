from __future__ import annotations

from pathlib import Path

import pandas as pd

from rkaa.infrastructure.visualization.temporal_profile_png import (
    write_temporal_profile_png,
)
from rkaa.infrastructure.visualization.weekly_profile_png import (
    write_weekly_profile_png,
)


def _assert_png(path: Path) -> None:
    assert path.exists()
    assert path.suffix == ".png"
    assert path.stat().st_size > 100
    assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_fr401_png_writer_generates_png_on_headless_backend(tmp_path: Path) -> None:
    overlay = pd.DataFrame(
        [
            {
                "ne_id": "NE1",
                "cell_id": "CELL_A",
                "kpi_name": "KPI_A",
                "temporal_profile": "OFF_PEAK",
                "minute_of_day": 0,
                "mean": 98.0,
            },
            {
                "ne_id": "NE1",
                "cell_id": "CELL_A",
                "kpi_name": "KPI_A",
                "temporal_profile": "TRANSITION",
                "minute_of_day": 360,
                "mean": 97.0,
            },
            {
                "ne_id": "NE1",
                "cell_id": "CELL_A",
                "kpi_name": "KPI_A",
                "temporal_profile": "BUSY",
                "minute_of_day": 480,
                "mean": 96.0,
            },
        ]
    )

    output = write_temporal_profile_png(
        overlay,
        ne_id="NE1",
        cell_id="CELL_A",
        kpi_name="KPI_A",
        output_path=tmp_path / "profile.svg",
    )

    _assert_png(output)
    assert output.name == "profile.png"


def test_fr402_png_writer_generates_png_on_headless_backend(tmp_path: Path) -> None:
    overlay = pd.DataFrame(
        [
            {
                "ne_id": "NE1",
                "cell_id": "CELL_A",
                "kpi_name": "KPI_A",
                "day_type": "WEEKDAY",
                "minute_of_day": 480,
                "mean": 98.0,
            },
            {
                "ne_id": "NE1",
                "cell_id": "CELL_A",
                "kpi_name": "KPI_A",
                "day_type": "WEEKEND",
                "minute_of_day": 480,
                "mean": 94.0,
            },
        ]
    )

    output = write_weekly_profile_png(
        overlay,
        ne_id="NE1",
        cell_id="CELL_A",
        kpi_name="KPI_A",
        output_path=tmp_path / "weekly_profile",
    )

    _assert_png(output)
    assert output.name == "weekly_profile.png"
