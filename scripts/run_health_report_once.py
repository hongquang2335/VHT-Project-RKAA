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

from rkaa.application.report_generator import (  # noqa: E402
    HealthReportArtifacts,
    generate_health_report_html,
    generate_health_report_pdf,
)


def _resolve(value: str | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily/Weekly Network Health Report (HTML/PDF)")
    parser.add_argument("--input", required=True, help="Clean canonical KPI long CSV")
    parser.add_argument(
        "--period",
        required=True,
        choices=["last-day", "distinctive-day", "last-week"],
        help=(
            "last-day/distinctive-day dùng chu kỳ 24h với references 24-72/144/288h; "
            "last-week dùng 7 ngày hiện tại so với 7 ngày liền trước"
        ),
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--format", choices=["html", "pdf"], help="Mặc định suy ra từ đuôi --output")
    parser.add_argument(
        "--daily-cycle-comparison",
        "--fr401-comparison",
        dest="daily_comparison",
        help="Artifact so sánh chu kỳ ngày; tên option cũ vẫn được hỗ trợ",
    )
    parser.add_argument(
        "--weekly-cycle-comparison",
        "--fr402-comparison",
        dest="weekly_comparison",
        help="Artifact so sánh chu kỳ tuần; tên option cũ vẫn được hỗ trợ",
    )
    parser.add_argument("--trend-summary")
    parser.add_argument(
        "--percent-direction-summary",
        "--fr404-summary",
        dest="percent_direction_summary",
    )
    parser.add_argument("--change-points")
    parser.add_argument("--knowledge-store")
    parser.add_argument("--title", default="RKAA - Báo cáo sức khỏe mạng")
    args = parser.parse_args()

    input_path = _resolve(args.input)
    assert input_path is not None
    if not input_path.exists():
        parser.error(f"Không tìm thấy input: {input_path}")

    output_path = _resolve(args.output)
    assert output_path is not None
    output_format = args.format
    if output_format is None:
        output_format = "pdf" if output_path.suffix.lower() == ".pdf" else "html"

    df = pd.read_csv(input_path)
    artifacts = HealthReportArtifacts(
        fr401_comparison=_resolve(args.daily_comparison),
        fr402_comparison=_resolve(args.weekly_comparison),
        trend_summary=_resolve(args.trend_summary),
        fr404_summary=_resolve(args.percent_direction_summary),
        change_points=_resolve(args.change_points),
        knowledge_store=_resolve(args.knowledge_store),
    )
    generator = generate_health_report_pdf if output_format == "pdf" else generate_health_report_html
    output, period, metadata = generator(
        df,
        period_kind=args.period,
        output_path=output_path,
        artifacts=artifacts,
        title=args.title,
    )
    print("Network Health Report")
    print("Format:", output_format.upper())
    print("Period:", period.label)
    print("Start:", period.start)
    print("End:", period.end)
    if period.distinctive_score is not None:
        print("Distinctive score:", round(period.distinctive_score, 6))
    print("Summary:", json.dumps(metadata, ensure_ascii=False))
    print("Output:", output)


if __name__ == "__main__":
    main()
