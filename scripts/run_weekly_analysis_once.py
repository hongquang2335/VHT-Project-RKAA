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
from rkaa.domain.temporal_analyzer import (  # noqa: E402
    CycleComparisonAnalyzer,
    WeeklyCycleAnalyzer,
)
from rkaa.infrastructure.config.cyclic_analysis_loader import (  # noqa: E402
    load_cyclic_analysis_config,
)
from rkaa.infrastructure.config.kpi_threshold_loader import (  # noqa: E402
    load_kpi_threshold_manager,
)
from rkaa.infrastructure.visualization.weekly_profile_png import (  # noqa: E402
    write_weekly_cycle_png,
)


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "FR-402: WEEKDAY/WEEKEND + day-of-week baseline + week-over-week "
            "comparison; month-over-month cấu hình được nhưng mặc định tắt"
        ),
    )
    parser.add_argument("--input", default="tmp/fr401/profiled_kpi.csv")
    parser.add_argument("--cyclic-config", default="configs/cyclic_analysis.yaml")
    parser.add_argument("--threshold-config", default="configs/kpi_thresholds.yaml")
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
        "--comparison-output",
        default="tmp/fr402/cycle_comparison.csv",
    )
    parser.add_argument(
        "--minimum-clean-days",
        type=int,
        default=14,
        help="BR-01: số ngày dữ liệu sạch tối thiểu để baseline được coi là đáng tin.",
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
    cyclic_config_path = _resolve_path(args.cyclic_config)
    threshold_config_path = _resolve_path(args.threshold_config)
    if not input_path.exists():
        parser.error(
            f"Không tìm thấy input FR-402: {input_path}. Hãy chạy FR-401 trước."
        )
    if not cyclic_config_path.exists():
        parser.error(f"Không tìm thấy cyclic config: {cyclic_config_path}")
    if not threshold_config_path.exists():
        parser.error(f"Không tìm thấy threshold config: {threshold_config_path}")
    if args.minimum_clean_days < 1:
        parser.error("--minimum-clean-days phải >= 1")
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
    day_type_baseline = engine.annotate_reliability(
        result.profiled_df,
        day_type_baseline,
        minimum_clean_days=args.minimum_clean_days,
    )
    weekday_baseline = engine.annotate_reliability(
        result.profiled_df,
        weekday_baseline,
        minimum_clean_days=args.minimum_clean_days,
    )

    cyclic_config = load_cyclic_analysis_config(cyclic_config_path)
    threshold_manager = load_kpi_threshold_manager(threshold_config_path)
    comparison = CycleComparisonAnalyzer(
        cyclic_config.statistical,
        threshold_manager=threshold_manager,
    ).compare_weekly_cycles(result.profiled_df, cyclic_config.fr402)

    profiled_path = _resolve_path(args.profiled_output)
    day_type_baseline_path = _resolve_path(args.day_type_baseline_output)
    weekday_baseline_path = _resolve_path(args.weekday_baseline_output)
    overlay_path = _resolve_path(args.overlay_output)
    comparison_path = _resolve_path(args.comparison_output)
    for path in (
        profiled_path,
        day_type_baseline_path,
        weekday_baseline_path,
        overlay_path,
        comparison_path,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)

    result.profiled_df.to_csv(profiled_path, index=False, encoding="utf-8-sig")
    day_type_baseline.to_csv(day_type_baseline_path, index=False, encoding="utf-8-sig")
    weekday_baseline.to_csv(weekday_baseline_path, index=False, encoding="utf-8-sig")
    result.overlay_df.to_csv(overlay_path, index=False, encoding="utf-8-sig")
    comparison.to_csv(comparison_path, index=False, encoding="utf-8-sig")

    counts = result.profiled_df["day_type"].value_counts().to_dict()
    anomaly_count = int(comparison["anomaly_flag"].sum()) if not comparison.empty else 0
    print("FR-402 Weekly Cycle Summary")
    print(f"Input records:         {len(df)}")
    print(f"WEEKDAY records:       {counts.get('WEEKDAY', 0)}")
    print(f"WEEKEND records:       {counts.get('WEEKEND', 0)}")
    print(f"Day-type baseline:     {len(day_type_baseline)}")
    print(f"Weekday baseline:      {len(weekday_baseline)}")
    print(f"Cycle comparisons:     {len(comparison)}")
    print(f"Anomaly flags:         {anomaly_count}")
    print(
        "Month-over-month:      "
        + ("ENABLED" if cyclic_config.fr402.previous_month_enabled else "DISABLED")
    )
    print("Profiled output:", profiled_path)
    print("Day-type baseline:", day_type_baseline_path)
    print("Weekday baseline:", weekday_baseline_path)
    print("Overlay output:", overlay_path)
    print("Cycle comparison:", comparison_path)

    if all(chart_values):
        chart_path = write_weekly_cycle_png(
            result.profiled_df,
            ne_id=args.chart_ne,
            cell_id=args.chart_cell,
            kpi_name=args.chart_kpi,
            output_path=_resolve_path(args.chart_output),
            anchor_end=result.profiled_df["timestamp"].max(),
            current_window_days=cyclic_config.fr402.current_window_days,
        )
        print("Chart output:", chart_path)


if __name__ == "__main__":
    main()
