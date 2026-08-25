from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rkaa.domain.data_collector.minio_collection_service import MinioCollectionService  # noqa: E402
from rkaa.domain.data_collector.minio_kpi_adapter import MinioKPIAdapter  # noqa: E402
from rkaa.domain.data_collector.minio_kpi_normalizer import MinioKPINormalizer  # noqa: E402
from rkaa.domain.data_collector.station_selection import normalize_station_ids  # noqa: E402
from rkaa.infrastructure.config.kpi_mapping_loader import load_kpi_mapping  # noqa: E402
from rkaa.infrastructure.config.station_list_loader import load_station_ids_from_yaml  # noqa: E402
from rkaa.infrastructure.data_store.local_metric_parquet import (  # noqa: E402
    LocalMetricParquetStore,
)
from rkaa.infrastructure.object_store.minio_duckdb import (  # noqa: E402
    create_minio_duckdb_connection,
    load_minio_config_from_env,
)


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def _resolve_station_ids(
    cli_station_ids: list[str] | None,
    stations_file: str | None,
) -> list[str]:
    """Resolve phạm vi NE khi không chạy chế độ ``--all-stations``.

    Nếu người dùng truyền ``--station`` thì chỉ dùng đúng danh sách CLI đó.
    Nếu không truyền ``--station`` mới fallback về ``--stations-file``.
    Cách này tránh việc một ``--station`` vô tình bị gộp thêm các NE trong
    ``configs/stations.yaml``.
    """
    if cli_station_ids:
        return normalize_station_ids(cli_station_ids)

    if stations_file:
        return normalize_station_ids(
            load_station_ids_from_yaml(_resolve_path(stations_file))
        )

    return []


def _select_mapping(mapping, *, metric_kind: str, metric_names: list[str] | None):
    selected = list(mapping)
    if metric_kind == "kpi":
        selected = [item for item in selected if not item.is_counter]
    elif metric_kind == "counter":
        selected = [item for item in selected if item.is_counter]

    wanted = {name.strip() for name in (metric_names or []) if name.strip()}
    if wanted:
        selected = [
            item
            for item in selected
            if item.canonical_name in wanted or item.source_column in wanted
        ]
        found = (
            {item.canonical_name for item in selected}
            | {item.source_column for item in selected}
        )
        missing = sorted(wanted - found)
        if missing:
            raise ValueError(f"Metric không có trong KPI config: {missing}")
    if not selected:
        raise ValueError("Không còn metric nào sau khi áp bộ lọc")
    return selected


def _iter_chunks(start: pd.Timestamp, end: pd.Timestamp, chunk_hours: int):
    current = start
    delta = pd.Timedelta(hours=chunk_hours)
    while current < end:
        chunk_end = min(current + delta, end)
        yield current, chunk_end
        current = chunk_end


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Thu thập lịch sử MinIO theo chunk và lưu local Parquet để tái sử dụng. "
            "MinIO chỉ được SELECT, không ghi/sửa/xóa."
        )
    )
    parser.add_argument("--start-time", required=True)
    parser.add_argument("--end-time", required=True)
    parser.add_argument("--chunk-hours", type=int, default=6)
    parser.add_argument("--granularity-minutes", type=int, default=5)
    parser.add_argument("--secret-file", default="secrets/minio.local")
    parser.add_argument(
        "--stations-file",
        default="configs/stations.yaml",
        help=(
            "Danh sách NE mặc định khi không truyền --station. "
            "Bị bỏ qua khi dùng --all-stations."
        ),
    )
    parser.add_argument(
        "--station",
        action="append",
        dest="station_ids",
        help=(
            "Chỉ lấy đúng NE này; có thể truyền nhiều lần. "
            "Nếu có --station thì không đọc stations.yaml."
        ),
    )
    parser.add_argument(
        "--all-stations",
        action="store_true",
        help=(
            "Không lọc NE; lấy toàn bộ station/NE và cell có trong MinIO "
            "ở khoảng thời gian được yêu cầu."
        ),
    )
    parser.add_argument("--kpi-config", default="configs/kpi_mapping.yaml")
    parser.add_argument("--metric-kind", choices=["all", "kpi", "counter"], default="kpi")
    parser.add_argument(
        "--metric",
        action="append",
        dest="metric_names",
        help="Chỉ lấy metric này; có thể truyền nhiều lần.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Thư mục snapshot. Mặc định: tmp/history_metrics_all khi "
            "--all-stations, ngược lại tmp/history_metrics."
        ),
    )
    parser.add_argument("--datetime-col", default=None)
    parser.add_argument("--ne-col", default=None)
    parser.add_argument("--cellname-col", default=None)
    parser.add_argument("--parquet-prefix", default="v3/*.parquet")
    parser.add_argument(
        "--limit-per-chunk",
        type=int,
        default=None,
        help="Chỉ dùng smoke test; mặc định không giới hạn để tránh cắt dữ liệu lịch sử.",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    start = pd.Timestamp(args.start_time)
    end = pd.Timestamp(args.end_time)
    if pd.isna(start) or pd.isna(end) or end <= start:
        parser.error("--end-time phải lớn hơn --start-time")
    if args.chunk_hours <= 0:
        parser.error("--chunk-hours phải > 0")
    if args.granularity_minutes <= 0:
        parser.error("--granularity-minutes phải > 0")

    if args.all_stations and args.station_ids:
        parser.error("Không dùng đồng thời --all-stations và --station")

    if args.all_stations:
        station_ids: list[str] = []
    else:
        station_ids = _resolve_station_ids(args.station_ids, args.stations_file)
        if not station_ids:
            parser.error(
                "Cần ít nhất một NE từ --station/--stations-file "
                "hoặc dùng --all-stations"
            )

    secret_file = _resolve_path(args.secret_file)
    if secret_file.exists():
        load_dotenv(secret_file)

    config = load_minio_config_from_env()
    conn = create_minio_duckdb_connection(config)

    datetime_col = (args.datetime_col or os.getenv("DATETIME_COL") or "datetime").strip('"\'')
    ne_col = (args.ne_col or os.getenv("NE_COL") or "ne").strip('"\'')
    cellname_col = (args.cellname_col or os.getenv("CELLNAME_COL") or "cellname").strip('"\'')

    mapping = load_kpi_mapping(_resolve_path(args.kpi_config))
    try:
        mapping = _select_mapping(
            mapping,
            metric_kind=args.metric_kind,
            metric_names=args.metric_names,
        )
    except ValueError as exc:
        parser.error(str(exc))

    normalizer = MinioKPINormalizer(
        kpi_mapping=mapping,
        datetime_col=datetime_col,
        ne_col=ne_col,
        cellname_col=cellname_col,
        granularity_minutes=args.granularity_minutes,
    )
    service = MinioCollectionService(
        adapter=MinioKPIAdapter(
            conn,
            bucket=config.bucket,
            parquet_prefix=args.parquet_prefix,
        ),
        normalizer=normalizer,
    )
    output_dir = args.output_dir or (
        "tmp/history_metrics_all" if args.all_stations else "tmp/history_metrics"
    )
    store = LocalMetricParquetStore(_resolve_path(output_dir))

    total_rows = 0
    written_chunks = 0
    skipped_chunks = 0
    try:
        for chunk_start, chunk_end in _iter_chunks(start, end, args.chunk_hours):
            target_name = (
                f"part-{chunk_start.strftime('%Y%m%dT%H%M%S')}"
                f"-{chunk_end.strftime('%Y%m%dT%H%M%S')}.parquet"
            )
            target = store.root / target_name
            if target.exists() and not args.overwrite:
                print(f"SKIP {chunk_start} -> {chunk_end}: {target.name}")
                skipped_chunks += 1
                continue

            if args.all_stations:
                # collect_once(..., cellname=None) không truyền station_ids xuống
                # query builder, vì vậy SQL chỉ lọc theo thời gian/metric và lấy
                # toàn bộ NE + cell có trong MinIO.
                long_df = service.collect_once(
                    start_time=chunk_start.isoformat(sep=" "),
                    end_time=chunk_end.isoformat(sep=" "),
                    limit=args.limit_per_chunk,
                )
            else:
                long_df = service.collect_for_stations(
                    start_time=chunk_start.isoformat(sep=" "),
                    end_time=chunk_end.isoformat(sep=" "),
                    station_ids=station_ids,
                    limit=args.limit_per_chunk,
                )
            store.write_chunk(
                long_df,
                start_time=chunk_start,
                end_time=chunk_end,
                overwrite=args.overwrite,
            )
            total_rows += len(long_df)
            written_chunks += 1
            print(
                f"WRITE {chunk_start} -> {chunk_end}: "
                f"rows={len(long_df):,} file={target.name}"
            )
    finally:
        conn.close()

    print("History collection complete")
    if args.all_stations:
        print("Station scope: ALL (không lọc theo ne)")
    else:
        print("Station scope: SELECTED")
        print("Stations:", len(station_ids), ", ".join(station_ids))
    print("Metrics:", len(mapping), f"kind={args.metric_kind}")
    print("Granularity minutes:", args.granularity_minutes)
    print("Chunks written:", written_chunks)
    print("Chunks skipped:", skipped_chunks)
    print("Rows written this run:", f"{total_rows:,}")
    print("Store:", store.root)


if __name__ == "__main__":
    main()