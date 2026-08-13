from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rkaa.domain.baseline_engine import BaselineEngine  # noqa: E402
from rkaa.domain.temporal_analyzer import WeeklyCycleAnalyzer  # noqa: E402
from rkaa.infrastructure.visualization.weekly_profile_svg import (  # noqa: E402
    write_weekly_profile_svg,
)


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FR-402: tách profile và baseline KPI theo WEEKDAY/WEEKEND",
    )
    parser.add_argument("--input", default="tmp/fr401/profiled_kpi.csv")
    parser.add_argument("--profiled-output", default="tmp/fr402/profiled_kpi.csv")
    parser.add_argument(
        "--day-type-baseline-output",
        default="tmp/fr402/day_type_baseline.csv",
    )
    parser.add_argument(
        "--weekday-baseline-output",
        default="tmp/fr402/weekday_baseline.csv",
    )
    parser.add_argument(
        "--overlay-output",
        default="tmp/fr402/weekday_weekend_overlay.csv",
    )
    parser.add_argument(
        "--min-weekday-dates",
        type=int,
        default=2,
        help=(
            "Số ngày lịch khác nhau tối thiểu để tạo baseline riêng cho từng thứ. "
            "SRS không quy định ngưỡng này; mặc định=2."
        ),
    )
    parser.add_argument("--chart-output")
    parser.add_argument("--chart-ne")
    parser.add_argument("--chart-cell")
    parser.add_argument("--chart-kpi")
    args = parser.parse_args()

    input_path = _resolve_path(args.input)
    if not input_path.exists():
        parser.error(
            f"Không tìm thấy input FR-402: {input_path}. Hãy chạy FR-401 trước."
        )
    if args.min_weekday_dates < 1:
        parser.error("--min-weekday-dates phải >= 1")

    chart_values = [args.chart_output, args.chart_ne, args.chart_cell, args.chart_kpi]
    if any(chart_values) and not all(chart_values):
        parser.error(
            "Để tạo biểu đồ, cần truyền đủ --chart-output --chart-ne --chart-cell --chart-kpi"
        )

    df = pd.read_csv(input_path)
    result = WeeklyCycleAnalyzer().analyze(df)
    engine = BaselineEngine()
    day_type_baseline = engine.compute_day_type(result.profiled_df)
    weekday_baseline = engine.compute_weekday(
        result.profiled_df,
        min_distinct_dates=args.min_weekday_dates,
    )

    profiled_path = _resolve_path(args.profiled_output)
    day_type_baseline_path = _resolve_path(args.day_type_baseline_output)
    weekday_baseline_path = _resolve_path(args.weekday_baseline_output)
    overlay_path = _resolve_path(args.overlay_output)
    for path in (
        profiled_path,
        day_type_baseline_path,
        weekday_baseline_path,
        overlay_path,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)

    result.profiled_df.to_csv(profiled_path, index=False, encoding="utf-8-sig")
    day_type_baseline.to_csv(day_type_baseline_path, index=False, encoding="utf-8-sig")
    weekday_baseline.to_csv(weekday_baseline_path, index=False, encoding="utf-8-sig")
    result.overlay_df.to_csv(overlay_path, index=False, encoding="utf-8-sig")

    counts = result.profiled_df["day_type"].value_counts().to_dict()
    print("Tổng hợp chu kỳ tuần FR-402")
    print(f"Số bản ghi đầu vào:    {len(df)}")
    print(f"Bản ghi WEEKDAY:       {counts.get('WEEKDAY', 0)}")
    print(f"Bản ghi WEEKEND:       {counts.get('WEEKEND', 0)}")
    print(f"Số dòng baseline loại ngày: {len(day_type_baseline)}")
    print(f"Số dòng baseline theo thứ: {len(weekday_baseline)}")
    print("Output đã gán profile:", profiled_path)
    print("Baseline theo loại ngày:", day_type_baseline_path)
    print("Baseline theo từng thứ:", weekday_baseline_path)
    print("Output overlay:", overlay_path)

    if all(chart_values):
        chart_path = write_weekly_profile_svg(
            result.overlay_df,
            ne_id=args.chart_ne,
            cell_id=args.chart_cell,
            kpi_name=args.chart_kpi,
            output_path=_resolve_path(args.chart_output),
        )
        print("Output biểu đồ:", chart_path)


if __name__ == "__main__":
    main()
