from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rkaa.domain.anomaly_detector import AnomalyDetectionService  # noqa: E402
from rkaa.infrastructure.config.kpi_threshold_loader import (  # noqa: E402
    load_threshold_manager,
)
from rkaa.infrastructure.visualization.impact_threshold_svg import (  # noqa: E402
    write_impact_threshold_svg,
)


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def _select_chart_row(df: pd.DataFrame, args: argparse.Namespace) -> pd.Series:
    selected = df[df["kpi_name"].astype(str) == args.chart_kpi]
    for column, value in (
        ("ne_id", args.chart_ne),
        ("cell_id", args.chart_cell),
        ("temporal_profile", args.chart_profile),
        ("day_type", args.chart_day_type),
    ):
        if value is not None and column in selected.columns:
            selected = selected[selected[column].astype(str) == value]
    if len(selected) != 1:
        raise ValueError(
            "Bộ lọc chart phải chọn đúng 1 dòng FR-302; "
            f"hiện chọn được {len(selected)} dòng"
        )
    return selected.iloc[0]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FR-302/FR-303: phát hiện KPI bất thường sau tác động",
    )
    parser.add_argument("--input", default="tmp/fr301/impact_analysis.csv")
    parser.add_argument("--baseline", default="tmp/fr402/day_type_baseline.csv")
    parser.add_argument("--threshold-config", default="configs/kpi_thresholds.yaml")
    parser.add_argument("--output", default="tmp/fr302/post_impact_anomalies.csv")
    parser.add_argument("--summary-output", default="tmp/fr302/anomaly_summary.csv")
    parser.add_argument("--chart-output")
    parser.add_argument("--chart-kpi")
    parser.add_argument("--chart-ne")
    parser.add_argument("--chart-cell")
    parser.add_argument("--chart-profile")
    parser.add_argument("--chart-day-type")
    args = parser.parse_args()

    input_path = _resolve_path(args.input)
    baseline_path = _resolve_path(args.baseline)
    threshold_path = _resolve_path(args.threshold_config)
    for label, path in (
        ("input FR-302", input_path),
        ("baseline lịch sử", baseline_path),
        ("threshold config", threshold_path),
    ):
        if not path.exists():
            parser.error(f"Không tìm thấy {label}: {path}")
    if bool(args.chart_output) != bool(args.chart_kpi):
        parser.error("Muốn tạo biểu đồ ngưỡng phải truyền cả --chart-output và --chart-kpi")

    impact_report = pd.read_csv(input_path)
    baseline = pd.read_csv(baseline_path)
    threshold_manager = load_threshold_manager(threshold_path)
    result = AnomalyDetectionService(threshold_manager).detect(impact_report, baseline)

    output_path = _resolve_path(args.output)
    summary_path = _resolve_path(args.summary_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False, encoding="utf-8-sig")

    severity_counts = result["anomaly_severity"].value_counts().to_dict()
    summary = pd.DataFrame(
        [
            {
                "row_count": len(result),
                "anomaly_count": int(result["anomaly_flag"].sum()),
                "normal_count": severity_counts.get("NORMAL", 0),
                "warning_count": severity_counts.get("WARNING", 0),
                "critical_count": severity_counts.get("CRITICAL", 0),
            }
        ]
    )
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

    print("Tổng hợp FR-302")
    print(f"Số nhóm phân tích: {len(result)}")
    print(f"Số nhóm bất thường: {int(result['anomaly_flag'].sum())}")
    print(f"WARNING: {severity_counts.get('WARNING', 0)}")
    print(f"CRITICAL: {severity_counts.get('CRITICAL', 0)}")
    print("Kết quả:", output_path)
    print("Tổng hợp:", summary_path)

    if args.chart_output:
        try:
            row = _select_chart_row(result, args)
        except ValueError as exc:
            parser.error(str(exc))
        policy = threshold_manager.get_policy(str(row["kpi_name"]))
        if policy is None:
            parser.error(f"KPI {row['kpi_name']} chưa có policy trong threshold config")
        chart_path = write_impact_threshold_svg(
            row.to_dict(),
            policy,
            _resolve_path(args.chart_output),
        )
        print("Threshold chart:", chart_path)


if __name__ == "__main__":
    main()
