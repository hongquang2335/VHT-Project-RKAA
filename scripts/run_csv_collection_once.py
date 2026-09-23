from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rkaa.domain.data_collector.csv_kpi_adapter import CSVKPIAdapter  # noqa: E402
from rkaa.domain.data_collector.minio_kpi_normalizer import MinioKPINormalizer  # noqa: E402
from rkaa.infrastructure.config.csv_adapter_loader import (  # noqa: E402
    apply_derived_metrics,
    load_csv_adapter_config,
    resolve_csv_metric_mapping,
)


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Demo adapter: wide KPI/counter CSV -> canonical RKAA long format",
    )
    parser.add_argument("--input", required=True, help="CSV KPI/counter nguồn")
    parser.add_argument(
        "--config",
        default="configs/csv_demo_adapter.yaml",
        help="Schema + KPI alias mapping cho CSV",
    )
    parser.add_argument("--start-time", default=None)
    parser.add_argument("--end-time", default=None)
    parser.add_argument("--cellname", default=None)
    parser.add_argument(
        "--station",
        action="append",
        dest="station_ids",
        help="Lọc NE; có thể truyền nhiều lần",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--discover-all",
        action="store_true",
        help=(
            "Tự nhận toàn bộ metric chưa khai báo; Pm.* hoặc cột kết thúc '(#)' "
            "được coi là counter, còn lại là KPI informational."
        ),
    )
    parser.add_argument(
        "--kpi-only",
        action="store_true",
        help=(
            "Demo analysis mode: chỉ emit KPI (không emit raw counter) để FR-203/"
            "FR-201/FR-401/FR-402 không phải xử lý hàng triệu counter không dùng."
        ),
    )
    parser.add_argument("--output", default="tmp/csv_demo_kpi_long.csv")
    args = parser.parse_args()

    input_path = _resolve_path(args.input)
    config_path = _resolve_path(args.config)
    if not input_path.exists():
        parser.error(f"Không tìm thấy input CSV: {input_path}")
    if not config_path.exists():
        parser.error(f"Không tìm thấy adapter config: {config_path}")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit phải > 0")
    if args.cellname and args.station_ids:
        parser.error("Chỉ dùng --cellname hoặc --station, không dùng đồng thời")

    config = load_csv_adapter_config(config_path)
    adapter = CSVKPIAdapter(
        input_path,
        dayfirst=config.source.dayfirst,
        encoding=config.source.encoding,
        delimiter=config.source.delimiter,
    )
    available_columns = adapter.available_columns()
    resolution = resolve_csv_metric_mapping(
        available_columns,
        config,
        enable_auto_discovery=True if args.discover_all else None,
    )
    selected_columns = resolution.source_columns()
    if args.station_ids:
        wide_df = adapter.fetch_kpi_wide_dataframe_for_stations(
            station_ids=args.station_ids,
            selected_columns=selected_columns,
            datetime_col=config.source.datetime_col,
            ne_col=config.source.ne_col,
            cellname_col=config.source.cellname_col,
            start_time=args.start_time,
            end_time=args.end_time,
            limit=args.limit,
        )
    else:
        wide_df = adapter.fetch_kpi_wide_dataframe(
            selected_columns=selected_columns,
            datetime_col=config.source.datetime_col,
            ne_col=config.source.ne_col,
            cellname_col=config.source.cellname_col,
            start_time=args.start_time,
            end_time=args.end_time,
            cellname=args.cellname,
            limit=args.limit,
        )

    wide_df = apply_derived_metrics(wide_df, resolution)
    resolved_mapping = resolution.normalizer_mapping()
    emission_mapping = (
        [item for item in resolved_mapping if not item.is_counter]
        if args.kpi_only
        else resolved_mapping
    )
    normalizer = MinioKPINormalizer(
        kpi_mapping=emission_mapping,
        datetime_col=config.source.datetime_col,
        ne_col=config.source.ne_col,
        cellname_col=config.source.cellname_col,
        granularity_minutes=config.source.granularity_minutes,
    )
    long_df = normalizer.normalize(wide_df)
    output_path = _resolve_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    long_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    all_mapping = resolved_mapping
    kpi_count = sum(not item.is_counter for item in all_mapping)
    counter_count = sum(item.is_counter for item in all_mapping)
    emitted_kpi_count = sum(not item.is_counter for item in emission_mapping)
    emitted_counter_count = sum(item.is_counter for item in emission_mapping)
    print("CSV Adapter Summary")
    print("Input:", input_path)
    print("Available source columns:", len(available_columns))
    print("Resolved KPI definitions:", kpi_count)
    print("Resolved counter definitions:", counter_count)
    print("KPI-only analysis mode:", "ON" if args.kpi_only else "OFF")
    print("Emitted KPI definitions:", emitted_kpi_count)
    print("Emitted counter definitions:", emitted_counter_count)
    print("Missing optional canonical metrics:", list(resolution.missing_optional))
    print("Auto-discovered metrics:", len(resolution.auto_discovered))
    print("Wide rows selected:", len(wide_df))
    print("Long rows emitted:", len(long_df))
    print("Output:", output_path)
    if not long_df.empty:
        print(long_df.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
