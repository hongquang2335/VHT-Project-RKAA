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
from rkaa.domain.data_collector.kpi_row_selector import select_kpi_rows  # noqa: E402
from rkaa.domain.temporal_analyzer import (  # noqa: E402
    CycleComparisonAnalyzer,
    TemporalAnalyzer,
)
from rkaa.domain.trend_analyzer.eligibility import ValidNECellSelector  # noqa: E402
from rkaa.infrastructure.config.cyclic_analysis_loader import (  # noqa: E402
    load_cyclic_analysis_config,
)
from rkaa.infrastructure.config.kpi_threshold_loader import (  # noqa: E402
    load_kpi_threshold_manager,
)
from rkaa.infrastructure.config.temporal_profile_loader import (  # noqa: E402
    load_temporal_profile_config,
)
from rkaa.infrastructure.visualization.temporal_profile_png import (  # noqa: E402
    write_temporal_cycle_png,
)


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "FR-401: profile ngày/đêm + baseline + so sánh chu kỳ 24h với "
            "TB ngày lịch sử 24→72h / 24→144h / 24→288h trước + anomaly flags FR-302/303"
        ),
    )
    parser.add_argument("--input", default="tmp/phase3/baseline_ready_kpi.csv")
    parser.add_argument("--config", default="configs/temporal_profile.yaml")
    parser.add_argument("--cyclic-config", default="configs/cyclic_analysis.yaml")
    parser.add_argument("--threshold-config", default="configs/kpi_thresholds.yaml")
    parser.add_argument("--granularity-minutes", type=int, default=5)
    parser.add_argument("--profiled-output", default="tmp/fr401/profiled_kpi.csv")
    parser.add_argument("--baseline-output", default="tmp/fr401/temporal_baseline.csv")
    parser.add_argument("--overlay-output", default="tmp/fr401/profile_overlay.csv")
    parser.add_argument("--comparison-output", default="tmp/fr401/cycle_comparison.csv")
    parser.add_argument("--pair-validity-output", default="tmp/fr401/pair_validity.csv")
    parser.add_argument(
        "--minimum-clean-days",
        type=int,
        default=14,
        help="BR-01: số ngày dữ liệu sạch tối thiểu để pair/baseline đáng tin.",
    )
    parser.add_argument(
        "--minimum-pair-completeness",
        type=float,
        default=0.70,
        help="Completeness tối thiểu của NE-Cell pair; mặc định theo BR-09=0.70.",
    )
    parser.add_argument("--chart-output")
    parser.add_argument("--chart-ne")
    parser.add_argument("--chart-cell")
    parser.add_argument("--chart-kpi")
    args = parser.parse_args()

    input_path = _resolve_path(args.input)
    config_path = _resolve_path(args.config)
    cyclic_config_path = _resolve_path(args.cyclic_config)
    threshold_config_path = _resolve_path(args.threshold_config)
    for label, path in (
        ("input FR-401", input_path),
        ("config FR-401", config_path),
        ("cyclic config", cyclic_config_path),
        ("threshold config", threshold_config_path),
    ):
        if not path.exists():
            parser.error(f"Không tìm thấy {label}: {path}")

    chart_values = [args.chart_output, args.chart_ne, args.chart_cell, args.chart_kpi]
    if any(chart_values) and not all(chart_values):
        parser.error(
            "Muốn sinh chart phải truyền đủ --chart-output --chart-ne --chart-cell --chart-kpi"
        )
    if args.minimum_clean_days < 1:
        parser.error("--minimum-clean-days phải >= 1")
    if args.granularity_minutes <= 0:
        parser.error("--granularity-minutes phải > 0")
    if not 0 < args.minimum_pair_completeness <= 1:
        parser.error("--minimum-pair-completeness phải nằm trong (0,1]")

    config = load_temporal_profile_config(config_path)
    cyclic_config = load_cyclic_analysis_config(cyclic_config_path)
    threshold_manager = load_kpi_threshold_manager(threshold_config_path)

    df = pd.read_csv(input_path)
    df, skipped_counters = select_kpi_rows(df)
    temporal_result = TemporalAnalyzer(config).analyze(df)

    selector = ValidNECellSelector(
        granularity_minutes=args.granularity_minutes,
        minimum_clean_days=args.minimum_clean_days,
        minimum_completeness=args.minimum_pair_completeness,
    )
    pair_validity = selector.evaluate(temporal_result.profiled_df)
    valid_profiled = selector.filter_valid(temporal_result.profiled_df, pair_validity)
    valid_overlay = TemporalAnalyzer.get_profile(valid_profiled)

    engine = BaselineEngine()
    baseline = engine.compute(valid_profiled)
    baseline = engine.annotate_reliability(
        valid_profiled,
        baseline,
        minimum_clean_days=args.minimum_clean_days,
    )
    comparison = CycleComparisonAnalyzer(
        cyclic_config.statistical,
        threshold_manager=threshold_manager,
    ).compare_daily_cycles(valid_profiled, cyclic_config.fr401)

    profiled_path = _resolve_path(args.profiled_output)
    baseline_path = _resolve_path(args.baseline_output)
    overlay_path = _resolve_path(args.overlay_output)
    comparison_path = _resolve_path(args.comparison_output)
    pair_validity_path = _resolve_path(args.pair_validity_output)
    for path in (
        profiled_path,
        baseline_path,
        overlay_path,
        comparison_path,
        pair_validity_path,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)

    valid_profiled.to_csv(profiled_path, index=False, encoding="utf-8-sig")
    baseline.to_csv(baseline_path, index=False, encoding="utf-8-sig")
    valid_overlay.to_csv(overlay_path, index=False, encoding="utf-8-sig")
    comparison.to_csv(comparison_path, index=False, encoding="utf-8-sig")
    pair_validity.to_csv(pair_validity_path, index=False, encoding="utf-8-sig")

    profiles = sorted(valid_profiled["temporal_profile"].unique().tolist())
    valid_pairs = int(pair_validity["is_valid_pair"].sum()) if not pair_validity.empty else 0
    anomaly_count = int(comparison["anomaly_flag"].sum()) if not comparison.empty else 0
    print("FR-401 Temporal Cycle Summary")
    print(f"Input KPI records: {len(df)}")
    print(f"Counter skipped:   {skipped_counters}")
    print(f"Valid NE-Cell:     {valid_pairs}/{len(pair_validity)}")
    print(f"Profiled records:  {len(valid_profiled)}")
    print(f"Profiles:          {', '.join(profiles)}")
    print(f"Baseline rows:     {len(baseline)}")
    print(f"Cycle comparisons: {len(comparison)}")
    print(f"Anomaly flags:     {anomaly_count}")
    print("Pair validity:", pair_validity_path)
    print("Profiled output:", profiled_path)
    print("Baseline output:", baseline_path)
    print("Overlay output:", overlay_path)
    print("Cycle comparison:", comparison_path)

    if all(chart_values):
        chart_path = write_temporal_cycle_png(
            valid_profiled,
            ne_id=args.chart_ne,
            cell_id=args.chart_cell,
            kpi_name=args.chart_kpi,
            output_path=_resolve_path(args.chart_output),
            anchor_end=valid_profiled["timestamp"].max(),
            current_window_hours=cyclic_config.fr401.current_window_hours,
            comparison_lags_hours=cyclic_config.fr401.comparison_lags_hours,
        )
        print("Chart output:", chart_path)


if __name__ == "__main__":
    main()
