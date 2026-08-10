from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Cho phép chạy script khi project dùng src layout
ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rkaa.domain.data_collector.minio_collection_service import MinioCollectionService
from rkaa.domain.data_collector.minio_kpi_adapter import MinioKPIAdapter
from rkaa.domain.data_collector.minio_kpi_normalizer import MinioKPINormalizer
from rkaa.domain.data_collector.station_selection import normalize_station_ids
from rkaa.infrastructure.config.station_list_loader import load_station_ids_from_yaml
from rkaa.infrastructure.object_store.minio_duckdb import (
    create_minio_duckdb_connection,
    load_minio_config_from_env,
)


def _resolve_station_ids(
    *,
    cli_station_ids: list[str] | None,
    stations_file: str | None,
) -> list[str]:
    station_ids = list(cli_station_ids or [])

    if stations_file:
        file_path = Path(stations_file)
        if not file_path.is_absolute():
            file_path = ROOT_DIR / file_path
        station_ids.extend(load_station_ids_from_yaml(file_path))

    return normalize_station_ids(station_ids)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--secret-file", default="secrets/minio.local")
    parser.add_argument("--start-time", required=True)
    parser.add_argument("--end-time", required=True)
    parser.add_argument("--cellname", default=None)
    parser.add_argument(
        "--station",
        action="append",
        dest="station_ids",
        help="Trạm cần lấy; có thể truyền nhiều lần",
    )
    parser.add_argument(
        "--stations-file",
        default="configs/stations.yaml",
        help=(
            "YAML chứa key stations với danh sách trạm cần lấy "
            "(mặc định: configs/stations.yaml)"
        ),
    )
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--output", default="tmp/minio_kpi_long.csv")
    parser.add_argument("--datetime-col", default=None)
    parser.add_argument("--cellname-col", default=None)
    parser.add_argument("--parquet-prefix", default="v3/*.parquet")
    args = parser.parse_args()

    station_ids = _resolve_station_ids(
        cli_station_ids=args.station_ids,
        stations_file=args.stations_file,
    )
    if args.cellname and station_ids:
        parser.error("Chỉ dùng --cellname hoặc --station/--stations-file, không dùng đồng thời")

    secret_file = ROOT_DIR / args.secret_file
    if secret_file.exists():
        load_dotenv(secret_file)

    config = load_minio_config_from_env()
    conn = create_minio_duckdb_connection(config)

    datetime_col = (
        args.datetime_col or os.getenv("DATETIME_COL") or "datetime"
    ).strip().strip('"').strip("'")

    cellname_col = (
        args.cellname_col or os.getenv("CELLNAME_COL") or "cellname"
    ).strip().strip('"').strip("'")

    normalizer = MinioKPINormalizer(
        datetime_col=datetime_col,
        cellname_col=cellname_col,
        granularity_minutes=15,
    )
    adapter = MinioKPIAdapter(
        conn,
        bucket=config.bucket,
        parquet_prefix=args.parquet_prefix,
    )
    service = MinioCollectionService(adapter=adapter, normalizer=normalizer)

    if station_ids:
        long_df = service.collect_for_stations(
            start_time=args.start_time,
            end_time=args.end_time,
            station_ids=station_ids,
            limit=args.limit,
        )
        print("Stations:", ", ".join(station_ids))
    else:
        long_df = service.collect_once(
            start_time=args.start_time,
            end_time=args.end_time,
            cellname=args.cellname,
            limit=args.limit,
        )

    output_path = ROOT_DIR / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    long_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print("Output:", output_path)
    print("Shape:", long_df.shape)
    print(long_df.head(30).to_string())


if __name__ == "__main__":
    main()
