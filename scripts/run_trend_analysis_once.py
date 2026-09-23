from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rkaa.domain.data_collector.kpi_row_selector import select_kpi_rows  # noqa: E402
from rkaa.domain.trend_analyzer import TrendAnalyzer  # noqa: E402
from rkaa.infrastructure.config.csv_adapter_loader import load_csv_adapter_config  # noqa: E402
from rkaa.infrastructure.config.fr4xx_loader import load_fr4xx_config  # noqa: E402
from rkaa.infrastructure.config.kpi_mapping_loader import load_kpi_mapping  # noqa: E402
from rkaa.infrastructure.visualization.trend_png import write_trend_png  # noqa: E402


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def _direction_preferences(kind: str, path: Path) -> dict[str, str]:
    if kind == "csv-adapter":
        config = load_csv_adapter_config(path)
        result = {
            item.canonical_name: item.direction_preference
            for item in config.metrics
            if not item.is_counter
        }
        result.update(
            {
                item.canonical_name: item.direction_preference
                for item in config.derived_metrics
                if not item.is_counter
            }
        )
        return result
    if kind == "minio":
        return {
            item.canonical_name: item.direction_preference
            for item in load_kpi_mapping(path)
            if not item.is_counter
        }
    if kind == "none":
        return {}
    raise ValueError(f"mapping-kind không hỗ trợ: {kind}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FR-403/404: STL trend trên từng KPI của valid NE-Cell pair",
    )
    parser.add_argument("--input", default="tmp/phase3/baseline_ready_kpi.csv")
    parser.add_argument("--granularity-minutes", type=int, default=5)
    parser.add_argument("--config", default="configs/fr4xx.yaml")
    parser.add_argument(
        "--mapping-kind",
        choices=["minio", "csv-adapter", "none"],
        default="minio",
    )
    parser.add_argument("--mapping-config", default="configs/kpi_mapping.yaml")
    parser.add_argument("--output-dir", default="tmp/fr403")
    parser.add_argument("--chart-output")
    parser.add_argument("--chart-ne")
    parser.add_argument("--chart-cell")
    parser.add_argument("--chart-kpi")
    args = parser.parse_args()

    if args.granularity_minutes <= 0:
        parser.error("--granularity-minutes phải > 0")
    chart_values = [args.chart_output, args.chart_ne, args.chart_cell, args.chart_kpi]
    if any(chart_values) and not all(chart_values):
        parser.error(
            "Để tạo biểu đồ FR-403, cần truyền đủ "
            "--chart-output --chart-ne --chart-cell --chart-kpi"
        )
    input_path = _path(args.input)
    if not input_path.exists():
        parser.error(f"Không tìm thấy input: {input_path}")

    df = pd.read_csv(input_path)
    df, skipped_counter_rows = select_kpi_rows(df)
    config = load_fr4xx_config(
        _path(args.config),
        granularity_minutes=args.granularity_minutes,
    )
    result = TrendAnalyzer(config.trend).analyze(
        df,
        direction_preferences=_direction_preferences(
            args.mapping_kind,
            _path(args.mapping_config),
        ),
    )

    output_dir = _path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pair_path = output_dir / "fr4xx_pair_validity.csv"
    trend_path = output_dir / "fr403_fr404_trend_summary.csv"
    components_path = output_dir / "fr403_stl_components.pkl"
    result.pair_validity_df.to_csv(pair_path, index=False, encoding="utf-8-sig")
    result.trend_df.to_csv(trend_path, index=False, encoding="utf-8-sig")
    # Internal hand-off cho FR-405; pickle tránh ghi hàng trăm nghìn dòng CSV.
    result.components_df.to_pickle(components_path)

    valid_pairs = int(result.pair_validity_df["is_valid_pair"].sum())
    summary = {
        "input_kpi_rows": len(df),
        "counter_rows_skipped": skipped_counter_rows,
        "total_pairs_with_usable_kpi_rows": len(result.pair_validity_df),
        "valid_pairs": valid_pairs,
        "invalid_pairs": len(result.pair_validity_df) - valid_pairs,
        "trend_series": len(result.trend_df),
        "eligible_trend_series": (
            int(result.trend_df["series_eligible"].sum())
            if not result.trend_df.empty
            else 0
        ),
        "components_rows": len(result.components_df),
    }
    (output_dir / "SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("Pair validity:", pair_path)
    print("Trend summary:", trend_path)
    print("FR-405 hand-off:", components_path)

    if all(chart_values):
        chart_path = write_trend_png(
            result.components_df,
            result.trend_df,
            ne_id=args.chart_ne,
            cell_id=args.chart_cell,
            kpi_name=args.chart_kpi,
            output_path=_path(args.chart_output),
        )
        print("FR-403 chart:", chart_path)


if __name__ == "__main__":
    main()
