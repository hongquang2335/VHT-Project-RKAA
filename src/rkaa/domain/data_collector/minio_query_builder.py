from __future__ import annotations

from dataclasses import dataclass

from rkaa.domain.data_collector.station_selection import normalize_station_ids


@dataclass(frozen=True)
class MinioKPIQuery:
    sql: str
    params: list[object]


def quote_identifier(name: str) -> str:
    if not isinstance(name, str):
        raise TypeError(
            f"Column name must be str, received {type(name).__name__}: {name!r}"
        )
    safe_name = name.replace('"', '""')
    return f'"{safe_name}"'


def _build_station_filter(
    *,
    cellname_col: str,
    station_ids: list[str],
    params: list[object],
) -> str:
    """Tạo điều kiện chỉ đọc cell thuộc các trạm được chọn.

    Quy ước hiện tại: cellname có dạng <station_id> hoặc <station_id>_...
    Ví dụ gHM00001 sẽ khớp gHM00001 và gHM00001_30n411.
    """
    clauses: list[str] = []
    quoted_cellname = quote_identifier(cellname_col)

    for station_id in station_ids:
        clauses.append(
            f"({quoted_cellname} = ? OR starts_with({quoted_cellname}, ?))"
        )
        params.extend([station_id, f"{station_id}_"])

    return f"({' OR '.join(clauses)})"


def build_minio_kpi_query(
    *,
    bucket: str,
    selected_columns: list[str],
    datetime_col: str,
    cellname_col: str,
    start_time: str,
    end_time: str,
    cellname: str | None = None,
    station_ids: list[str] | None = None,
    parquet_prefix: str = "v3/*.parquet",
    limit: int | None = None,
) -> MinioKPIQuery:
    if not selected_columns:
        raise ValueError("selected_columns must not be empty")

    normalized_station_ids = normalize_station_ids(station_ids or [])
    if cellname and normalized_station_ids:
        raise ValueError("Chỉ dùng cellname hoặc station_ids, không dùng đồng thời")

    parquet_uri = f"s3://{bucket}/{parquet_prefix}"
    select_expr = ", ".join(quote_identifier(col) for col in selected_columns)

    where_clauses = [
        f"{quote_identifier(datetime_col)} >= ?",
        f"{quote_identifier(datetime_col)} < ?",
    ]
    params: list[object] = [start_time, end_time]

    if cellname:
        where_clauses.append(f"{quote_identifier(cellname_col)} = ?")
        params.append(cellname)

    if normalized_station_ids:
        where_clauses.append(
            _build_station_filter(
                cellname_col=cellname_col,
                station_ids=normalized_station_ids,
                params=params,
            )
        )

    sql = f"""
        SELECT {select_expr}
        FROM read_parquet('{parquet_uri}')
        WHERE {" AND ".join(where_clauses)}
    """

    if limit is not None:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        sql += f"\nLIMIT {int(limit)}"

    return MinioKPIQuery(sql=sql, params=params)
