from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rkaa.domain.impact_analyzer import ImpactAnalyzerService  # noqa: E402
from rkaa.infrastructure.config.kpi_threshold_loader import (  # noqa: E402
    load_threshold_manager,
)
from rkaa.infrastructure.data_store.database import (  # noqa: E402
    create_sqlite_connection,
    initialize_metadata_schema,
)
from rkaa.infrastructure.data_store.impact_repository import (  # noqa: E402
    SQLiteImpactRepository,
)


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FR-301: phân tích KPI trước/sau Impact Event",
    )
    parser.add_argument("--input", default="tmp/fr402/profiled_kpi.csv")
    parser.add_argument("--database", default="tmp/rkaa_metadata.db")
    parser.add_argument("--impact-id", required=True)
    parser.add_argument("--window-hours", type=float, default=24.0)
    parser.add_argument(
        "--kpi",
        action="append",
        default=None,
        help="Có thể lặp lại --kpi; nếu bỏ qua sẽ phân tích toàn bộ KPI có dữ liệu",
    )
    parser.add_argument("--threshold-config", default="configs/kpi_thresholds.yaml")
    parser.add_argument("--output", default="tmp/fr301/impact_analysis.csv")
    parser.add_argument("--pre-output", default="tmp/fr301/pre_window.csv")
    parser.add_argument("--post-output", default="tmp/fr301/post_window.csv")
    parser.add_argument("--summary-output", default="tmp/fr301/impact_analysis_summary.csv")
    args = parser.parse_args()

    input_path = _resolve_path(args.input)
    database_path = _resolve_path(args.database)
    threshold_path = _resolve_path(args.threshold_config)
    if not input_path.exists():
        parser.error(f"Không tìm thấy input FR-301: {input_path}. Hãy chạy FR-402 trước.")
    if not database_path.exists():
        parser.error(f"Không tìm thấy metadata database: {database_path}")
    if not threshold_path.exists():
        parser.error(f"Không tìm thấy threshold config: {threshold_path}")
    if args.window_hours <= 0:
        parser.error("--window-hours phải > 0")

    connection = create_sqlite_connection(database_path)
    try:
        initialize_metadata_schema(connection)
        repository = SQLiteImpactRepository(connection)
        event = repository.get_by_id(args.impact_id)
        if event is None:
            parser.error(f"Không tìm thấy impact_id={args.impact_id}")

        threshold_manager = load_threshold_manager(threshold_path)
        data = pd.read_csv(input_path)
        result = ImpactAnalyzerService().analyze(
            data,
            event,
            window_hours=args.window_hours,
            kpi_names=args.kpi,
            direction_preferences=threshold_manager.direction_preferences(),
        )
    finally:
        connection.close()

    output_path = _resolve_path(args.output)
    pre_path = _resolve_path(args.pre_output)
    post_path = _resolve_path(args.post_output)
    summary_path = _resolve_path(args.summary_output)
    for path in (output_path, pre_path, post_path, summary_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    result.report_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    result.pre_df.to_csv(pre_path, index=False, encoding="utf-8-sig")
    result.post_df.to_csv(post_path, index=False, encoding="utf-8-sig")

    trend_counts = (
        result.report_df["trend_assessment"].value_counts().to_dict()
        if "trend_assessment" in result.report_df.columns
        else {}
    )
    summary = pd.DataFrame(
        [
            {
                "impact_id": event.impact_id,
                "ne_id": event.ne_id,
                "cell_id": event.cell_id,
                "impact_type": event.impact_type,
                "window_hours": args.window_hours,
                "pre_record_count": len(result.pre_df),
                "post_record_count": len(result.post_df),
                "comparison_count": len(result.report_df),
                "improved_count": trend_counts.get("IMPROVED", 0),
                "degraded_count": trend_counts.get("DEGRADED", 0),
                "unchanged_count": trend_counts.get("UNCHANGED", 0),
                "informational_count": trend_counts.get("INFORMATIONAL", 0),
                "insufficient_data_count": trend_counts.get("INSUFFICIENT_DATA", 0),
            }
        ]
    )
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

    print("Tổng hợp FR-301")
    print(f"Impact ID:             {event.impact_id}")
    print(f"Số record pre-window:  {len(result.pre_df)}")
    print(f"Số record post-window: {len(result.post_df)}")
    print(f"Số nhóm được so sánh:  {len(result.report_df)}")
    print("Kết quả:", output_path)
    print("Pre-window:", pre_path)
    print("Post-window:", post_path)
    print("Tổng hợp:", summary_path)


if __name__ == "__main__":
    main()
