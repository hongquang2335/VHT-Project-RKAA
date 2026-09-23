from __future__ import annotations

from pathlib import Path

import pandas as pd

from rkaa.infrastructure.visualization.temporal_profile_png import (
    build_daily_cycle_windows,
    write_temporal_cycle_png,
    write_temporal_profile_png,
)
from rkaa.infrastructure.visualization.weekly_profile_png import (
    build_weekly_windows,
    write_weekly_cycle_png,
    write_weekly_profile_png,
)


def _assert_png(path: Path) -> None:
    assert path.exists()
    assert path.suffix == ".png"
    assert path.stat().st_size > 100
    assert path.read_bytes()[:8] == bytes([137, 80, 78, 71, 13, 10, 26, 10])



def test_fr401_png_writer_generates_png_on_headless_backend(tmp_path: Path) -> None:
    overlay = pd.DataFrame(
        [
            {"ne_id": "NE1", "cell_id": "CELL_A", "kpi_name": "KPI_A", "temporal_profile": "OFF_PEAK", "minute_of_day": 0, "mean": 98.0},
            {"ne_id": "NE1", "cell_id": "CELL_A", "kpi_name": "KPI_A", "temporal_profile": "TRANSITION", "minute_of_day": 360, "mean": 97.0},
            {"ne_id": "NE1", "cell_id": "CELL_A", "kpi_name": "KPI_A", "temporal_profile": "BUSY", "minute_of_day": 480, "mean": 96.0},
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
            {"ne_id": "NE1", "cell_id": "CELL_A", "kpi_name": "KPI_A", "day_type": "WEEKDAY", "minute_of_day": 480, "mean": 98.0},
            {"ne_id": "NE1", "cell_id": "CELL_A", "kpi_name": "KPI_A", "day_type": "WEEKEND", "minute_of_day": 480, "mean": 94.0},
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


def test_fr401_fr402_use_half_size_demo_canvas() -> None:
    from rkaa.infrastructure.visualization.temporal_profile_png import FIGURE_SIZE_INCHES as FR401_SIZE
    from rkaa.infrastructure.visualization.weekly_profile_png import FIGURE_SIZE_INCHES as FR402_SIZE

    assert FR401_SIZE == (6.0, 2.6)
    assert FR402_SIZE == (6.0, 2.6)


def _fr401_profiled_hourly() -> pd.DataFrame:
    timestamps = pd.date_range("2026-09-01T00:00:00Z", periods=14 * 24, freq="h")
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "ne_id": "NE1",
            "cell_id": "CELL_A",
            "kpi_name": "KPI_A",
            "value": [90.0 + (index % 24) / 10 for index in range(len(timestamps))],
            "temporal_profile": [
                "OFF_PEAK" if hour in {0,1,2,3,4,5,22,23} else "TRANSITION" if hour in {6,21} else "BUSY"
                for hour in timestamps.hour
            ],
            "minute_of_day": [hour * 60 for hour in timestamps.hour],
            "time_of_day": [f"{hour:02d}:00" for hour in timestamps.hour],
        }
    )
    return frame


def _fr402_profiled_hourly() -> pd.DataFrame:
    timestamps = pd.date_range("2026-09-01T00:00:00Z", periods=21 * 24, freq="h")
    names = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "ne_id": "NE1",
            "cell_id": "CELL_A",
            "kpi_name": "KPI_A",
            "value": [90.0 + (index % 24) / 20 for index in range(len(timestamps))],
            "day_type": ["WEEKDAY" if ts.dayofweek <= 4 else "WEEKEND" for ts in timestamps],
            "day_of_week": [names[ts.dayofweek] for ts in timestamps],
            "minute_of_day": [ts.hour * 60 for ts in timestamps],
        }
    )


def test_fr401_cycle_windows_are_current_plus_three_historical_means() -> None:
    profiled = _fr401_profiled_hourly()
    anchor = profiled["timestamp"].max()
    windows = build_daily_cycle_windows(
        profiled,
        ne_id="NE1",
        cell_id="CELL_A",
        kpi_name="KPI_A",
        anchor_end=anchor,
        current_window_hours=24,
        comparison_lags_hours=(72, 144, 288),
    )

    assert [window.label for window in windows] == [
        "CURRENT",
        "24H_TO_72H_AVG",
        "24H_TO_144H_AVG",
        "24H_TO_288H_AVG",
    ]
    assert len(windows[0].data) == 24
    assert windows[1].data["minute_of_day"].nunique() == 24
    assert windows[2].data["minute_of_day"].nunique() == 24
    assert windows[3].data["minute_of_day"].nunique() == 24


def test_fr401_cycle_png_writer_generates_four_cycle_png(tmp_path: Path) -> None:
    profiled = _fr401_profiled_hourly()
    output = write_temporal_cycle_png(
        profiled,
        ne_id="NE1",
        cell_id="CELL_A",
        kpi_name="KPI_A",
        output_path=tmp_path / "cycles.png",
        anchor_end=profiled["timestamp"].max(),
        current_window_hours=24,
        comparison_lags_hours=(72, 144, 288),
    )

    _assert_png(output)


def test_fr402_builds_current_and_previous_week_windows() -> None:
    profiled = _fr402_profiled_hourly()
    current, previous = build_weekly_windows(
        profiled,
        ne_id="NE1",
        cell_id="CELL_A",
        kpi_name="KPI_A",
        anchor_end=profiled["timestamp"].max(),
        current_window_days=7,
    )

    assert current.label == "CURRENT_WEEK"
    assert previous.label == "PREVIOUS_WEEK"
    assert len(current.data) == 7 * 24
    assert len(previous.data) == 7 * 24


def test_fr402_cycle_png_writer_generates_four_cycle_png(tmp_path: Path) -> None:
    profiled = _fr402_profiled_hourly()
    output = write_weekly_cycle_png(
        profiled,
        ne_id="NE1",
        cell_id="CELL_A",
        kpi_name="KPI_A",
        output_path=tmp_path / "fr402.png",
        anchor_end=profiled["timestamp"].max(),
        current_window_days=7,
    )

    _assert_png(output)
