from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rkaa.domain.data_collector.kpi_row_selector import split_metric_rows  # noqa: E402
from rkaa.domain.data_quality.service import DataQualityService  # noqa: E402
from rkaa.infrastructure.config.data_quality_loader import (  # noqa: E402
    load_data_quality_config,
)


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FR-203: chuẩn hóa và kiểm tra chất lượng dữ liệu KPI/Counter",
    )
    parser.add_argument("--input", default="tmp/minio_kpi_long.csv")
    parser.add_argument("--config", default="configs/data_quality.yaml")
    parser.add_argument(
        "--quality-output",
        default="tmp/fr203/quality_checked_metrics.csv",
        help="Toàn bộ KPI + counter sau FR-203.",
    )
    parser.add_argument(
        "--observation-kpi-output",
        default="tmp/phase3/observation_kpi.csv",
        help="Snapshot KPI gần raw + quality flags cho luồng observation.",
    )
    parser.add_argument(
        "--counter-output",
        default="tmp/phase3/quality_checked_counter.csv",
        help="Counter sau FR-203; không qua FR-201 ở Pha 3.",
    )
    parser.add_argument(
        "--issues-output",
        default="tmp/fr203/data_quality_issues.csv",
    )
    parser.add_argument(
        "--summary-output",
        default="tmp/fr203/data_quality_summary.csv",
    )
    args = parser.parse_args()

    input_path = _resolve_path(args.input)
    config_path = _resolve_path(args.config)
    quality_path = _resolve_path(args.quality_output)
    observation_kpi_path = _resolve_path(args.observation_kpi_output)
    counter_path = _resolve_path(args.counter_output)
    issues_path = _resolve_path(args.issues_output)
    summary_path = _resolve_path(args.summary_output)

    if not input_path.exists():
        parser.error(f"Không tìm thấy input CSV: {input_path}")
    if not config_path.exists():
        parser.error(f"Không tìm thấy config FR-203: {config_path}")

    config = load_data_quality_config(config_path)
    df = pd.read_csv(input_path)
    result = DataQualityService(config).check(df)
    observation_kpi_df, counter_df = split_metric_rows(result.quality_df)

    for path in (
        quality_path,
        observation_kpi_path,
        counter_path,
        issues_path,
        summary_path,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)

    result.quality_df.to_csv(quality_path, index=False, encoding="utf-8-sig")
    observation_kpi_df.to_csv(observation_kpi_path, index=False, encoding="utf-8-sig")
    counter_df.to_csv(counter_path, index=False, encoding="utf-8-sig")
    result.issues_df.to_csv(issues_path, index=False, encoding="utf-8-sig")
    result.summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")

    print("FR-203 Data Quality Summary")
    print(f"Input records:       {result.summary['input_records']}")
    print(f"Output records:      {result.summary['output_records']}")
    print(f"Observation KPI:     {len(observation_kpi_df)}")
    print(f"Quality Counter:     {len(counter_df)}")
    print(f"Issue records:       {result.summary['issue_records']}")
    print(f"Gaps > 2h:           {result.summary['gaps_over_2h']}")
    print("Issues by type:")
    issues_by_type = result.summary.get("issues_by_type", {})
    if isinstance(issues_by_type, dict):
        for name, count in issues_by_type.items():
            print(f"  {name}: {count}")
    if int(result.summary["gaps_over_2h"]) > 0:
        print("CẢNH BÁO FR-203: phát hiện gap dữ liệu > 2 giờ", file=sys.stderr)

    print("Quality output:", quality_path)
    print("Observation KPI output:", observation_kpi_path)
    print("Counter output:", counter_path)
    print("Issues output:", issues_path)
    print("Summary output:", summary_path)


if __name__ == "__main__":
    main()
