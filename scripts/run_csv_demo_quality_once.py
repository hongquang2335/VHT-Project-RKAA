from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rkaa.demo.csv_demo_quality import fast_check_csv_demo  # noqa: E402
from rkaa.infrastructure.config.data_quality_loader import load_data_quality_config  # noqa: E402


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Demo-only vectorized FR-203-compatible preparation for CSV adapter KPI rows",
    )
    parser.add_argument("--input", default="tmp/demo/kpi_analysis_input.csv")
    parser.add_argument("--config", default="configs/data_quality_demo_hourly.yaml")
    parser.add_argument("--quality-output", default="tmp/demo/fr203/quality_checked_kpi.csv")
    parser.add_argument("--observation-output", default="tmp/demo/phase3/observation_kpi.csv")
    parser.add_argument("--issues-output", default="tmp/demo/fr203/data_quality_issues.csv")
    parser.add_argument("--summary-output", default="tmp/demo/fr203/data_quality_summary.csv")
    args = parser.parse_args()

    input_path = _resolve_path(args.input)
    config_path = _resolve_path(args.config)
    if not input_path.exists():
        parser.error(f"Không tìm thấy input CSV: {input_path}")
    if not config_path.exists():
        parser.error(f"Không tìm thấy demo quality config: {config_path}")

    config = load_data_quality_config(config_path)
    df = pd.read_csv(input_path)
    if "is_counter" in df.columns:
        raw = df["is_counter"]
        if pd.api.types.is_bool_dtype(raw.dtype):
            has_counter = bool(raw.fillna(False).any())
        else:
            has_counter = bool(raw.astype("string").str.lower().isin({"1", "true", "yes", "y"}).any())
        if has_counter:
            parser.error("Demo fast-path chỉ nhận KPI rows; hãy chạy adapter với --kpi-only")

    result = fast_check_csv_demo(df, config)
    outputs = {
        "quality": _resolve_path(args.quality_output),
        "observation": _resolve_path(args.observation_output),
        "issues": _resolve_path(args.issues_output),
        "summary": _resolve_path(args.summary_output),
    }
    for path in outputs.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    result.quality_df.to_csv(outputs["quality"], index=False, encoding="utf-8-sig")
    result.quality_df.to_csv(outputs["observation"], index=False, encoding="utf-8-sig")
    result.issues_df.to_csv(outputs["issues"], index=False, encoding="utf-8-sig")
    result.summary_df.to_csv(outputs["summary"], index=False, encoding="utf-8-sig")

    print("CSV Demo Quality Summary (fast path; core FR-203 unchanged)")
    print(f"Input records:       {result.summary['input_records']}")
    print(f"Output records:      {result.summary['output_records']}")
    print(f"Issue records:       {result.summary['issue_records']}")
    print(f"Gaps > 2h:           {result.summary['gaps_over_2h']}")
    print("Issues by type:")
    for name, count in result.summary.get("issues_by_type", {}).items():
        print(f"  {name}: {count}")
    print("Local spike:         DISABLED in demo fast-path")
    print("Observation output:", outputs["observation"])
    print("Issues output:", outputs["issues"])
    print("Summary output:", outputs["summary"])


if __name__ == "__main__":
    main()
