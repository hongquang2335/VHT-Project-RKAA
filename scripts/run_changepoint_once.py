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

from rkaa.domain.anomaly_detector import ChangePointDetector  # noqa: E402
from rkaa.infrastructure.config.fr4xx_loader import load_fr4xx_config  # noqa: E402


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FR-405: PELT level/variance change-point từ STL components FR-403",
    )
    parser.add_argument("--input", default="tmp/fr403/fr403_stl_components.pkl")
    parser.add_argument("--granularity-minutes", type=int, default=5)
    parser.add_argument("--config", default="configs/fr4xx.yaml")
    parser.add_argument("--output-dir", default="tmp/fr405")
    args = parser.parse_args()

    if args.granularity_minutes <= 0:
        parser.error("--granularity-minutes phải > 0")
    input_path = _path(args.input)
    if not input_path.exists():
        parser.error(f"Không tìm thấy STL hand-off: {input_path}")

    components = pd.read_pickle(input_path)
    config = load_fr4xx_config(
        _path(args.config),
        granularity_minutes=args.granularity_minutes,
    )
    result = ChangePointDetector(config.change_point).detect(components)

    output_dir = _path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "fr405_change_points.csv"
    result.to_csv(output_path, index=False, encoding="utf-8-sig")
    summary = {
        "component_rows": len(components),
        "series": (
            int(components[["ne_id", "cell_id", "kpi_name"]].drop_duplicates().shape[0])
            if not components.empty
            else 0
        ),
        "change_points": len(result),
        "engineer_review_alerts": (
            int(result["alert_required"].fillna(False).astype(bool).sum())
            if not result.empty and "alert_required" in result.columns
            else 0
        ),
        "series_with_change_points": (
            int(result[["ne_id", "cell_id", "kpi_name"]].drop_duplicates().shape[0])
            if not result.empty
            else 0
        ),
    }
    (output_dir / "SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("Change-point output:", output_path)


if __name__ == "__main__":
    main()
