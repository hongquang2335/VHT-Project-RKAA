from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rkaa.infrastructure.data_store.local_metric_parquet import (  # noqa: E402
    LocalMetricParquetStore,
)


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Query một phần history snapshot đã lưu bằng DuckDB/Parquet."
    )
    parser.add_argument("--store", default="tmp/history_metrics")
    parser.add_argument("--start-time", default=None)
    parser.add_argument("--end-time", default=None)
    parser.add_argument("--ne", action="append", dest="ne_ids")
    parser.add_argument("--cell", action="append", dest="cell_ids")
    parser.add_argument("--metric", action="append", dest="metric_names")
    parser.add_argument("--metric-kind", choices=["all", "kpi", "counter"], default="all")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--count-only", action="store_true")
    parser.add_argument(
        "--output",
        default=None,
        help="Nếu truyền, ghi phần dữ liệu query ra CSV để kiểm tra hoặc đưa tiếp vào FR-203.",
    )
    args = parser.parse_args()

    store = LocalMetricParquetStore(_resolve_path(args.store))
    limit = 1 if args.count_only else args.limit
    try:
        df, total = store.query(
            start_time=args.start_time,
            end_time=args.end_time,
            ne_ids=args.ne_ids,
            cell_ids=args.cell_ids,
            metric_names=args.metric_names,
            metric_kind=args.metric_kind,
            limit=limit,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    print("Matched rows:", f"{total:,}")
    if args.count_only:
        return

    print("Returned rows:", f"{len(df):,}")
    if not df.empty:
        print(df.to_string(index=False))

    if args.output:
        output = _resolve_path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output, index=False, encoding="utf-8-sig")
        print("Output:", output)


if __name__ == "__main__":
    main()
