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
from rkaa.domain.temporal_analyzer import TemporalAnalyzer  # noqa: E402
from rkaa.infrastructure.config.temporal_profile_loader import (  # noqa: E402
    load_temporal_profile_config,
)
from rkaa.infrastructure.visualization.temporal_profile_svg import (  # noqa: E402
    write_temporal_profile_svg,
)


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FR-401: phân tích profile ngày/đêm và baseline theo profile",
    )
    parser.add_argument("--input", default="tmp/fr201/cleaned_kpi.csv")
    parser.add_argument("--config", default="configs/temporal_profile.yaml")
    parser.add_argument("--profiled-output", default="tmp/fr401/profiled_kpi.csv")
    parser.add_argument("--baseline-output", default="tmp/fr401/temporal_baseline.csv")
    parser.add_argument("--overlay-output", default="tmp/fr401/profile_overlay.csv")
    parser.add_argument("--chart-output")
    parser.add_argument("--chart-ne")
    parser.add_argument("--chart-cell")
    parser.add_argument("--chart-kpi")
    args = parser.parse_args()

    input_path = _resolve_path(args.input)
    config_path = _resolve_path(args.config)
    if not input_path.exists():
        parser.error(f"Không tìm thấy input FR-401: {input_path}")
    if not config_path.exists():
        parser.error(f"Không tìm thấy config FR-401: {config_path}")

    chart_values = [args.chart_output, args.chart_ne, args.chart_cell, args.chart_kpi]
    if any(chart_values) and not all(chart_values):
        parser.error(
            "Muốn sinh chart phải truyền đủ --chart-output --chart-ne --chart-cell --chart-kpi"
        )

    config = load_temporal_profile_config(config_path)
    df = pd.read_csv(input_path)
    result = TemporalAnalyzer(config).analyze(df)
    baseline = BaselineEngine().compute(result.profiled_df)

    profiled_path = _resolve_path(args.profiled_output)
    baseline_path = _resolve_path(args.baseline_output)
    overlay_path = _resolve_path(args.overlay_output)
    for path in (profiled_path, baseline_path, overlay_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    result.profiled_df.to_csv(profiled_path, index=False, encoding="utf-8-sig")
    baseline.to_csv(baseline_path, index=False, encoding="utf-8-sig")
    result.overlay_df.to_csv(overlay_path, index=False, encoding="utf-8-sig")

    profiles = sorted(result.profiled_df["temporal_profile"].unique().tolist())
    print("FR-401 Temporal Profile Summary")
    print(f"Input records:    {len(df)}")
    print(f"Profiled records: {len(result.profiled_df)}")
    print(f"Profiles:         {', '.join(profiles)}")
    print(f"Baseline rows:    {len(baseline)}")
    print("Profiled output:", profiled_path)
    print("Baseline output:", baseline_path)
    print("Overlay output:", overlay_path)

    if all(chart_values):
        chart_path = write_temporal_profile_svg(
            result.overlay_df,
            ne_id=args.chart_ne,
            cell_id=args.chart_cell,
            kpi_name=args.chart_kpi,
            output_path=_resolve_path(args.chart_output),
        )
        print("Chart output:", chart_path)


if __name__ == "__main__":
    main()
