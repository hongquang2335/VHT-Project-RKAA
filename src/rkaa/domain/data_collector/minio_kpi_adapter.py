from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

from rkaa.domain.data_collector.minio_query_builder import build_minio_kpi_query
from rkaa.domain.data_collector.station_selection import normalize_station_ids


class MinioKPIAdapter:
    def __init__(
        self,
        conn: DuckDBPyConnection,
        *,
        bucket: str,
        parquet_prefix: str = "v3/*.parquet",
    ) -> None:
        self.conn = conn
        self.bucket = bucket
        self.parquet_prefix = parquet_prefix

    def fetch_kpi_wide_dataframe(
        self,
        *,
        selected_columns: list[str],
        datetime_col: str,
        ne_col: str,
        cellname_col: str,
        start_time: str,
        end_time: str,
        cellname: str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """Đọc theo thời gian hoặc lọc chính xác một cell; chỉ dùng SELECT."""
        query = build_minio_kpi_query(
            bucket=self.bucket,
            selected_columns=selected_columns,
            datetime_col=datetime_col,
            ne_col=ne_col,
            cellname_col=cellname_col,
            start_time=start_time,
            end_time=end_time,
            cellname=cellname,
            parquet_prefix=self.parquet_prefix,
            limit=limit,
        )
        return self._execute_query(query.sql, query.params)

    def fetch_kpi_wide_dataframe_for_stations(
        self,
        *,
        station_ids: list[str],
        selected_columns: list[str],
        datetime_col: str,
        ne_col: str,
        cellname_col: str,
        start_time: str,
        end_time: str,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """Đọc KPI chỉ cho danh sách NE/trạm mong muốn theo cột ``ne``.

        Phương thức chỉ sinh SELECT trên Parquet MinIO, không ghi/sửa/xóa dữ liệu nguồn.
        """
        normalized_station_ids = normalize_station_ids(station_ids)
        if not normalized_station_ids:
            return pd.DataFrame(columns=selected_columns)

        query = build_minio_kpi_query(
            bucket=self.bucket,
            selected_columns=selected_columns,
            datetime_col=datetime_col,
            ne_col=ne_col,
            cellname_col=cellname_col,
            start_time=start_time,
            end_time=end_time,
            station_ids=normalized_station_ids,
            parquet_prefix=self.parquet_prefix,
            limit=limit,
        )
        return self._execute_query(query.sql, query.params)

    def _execute_query(self, sql: str, params: list[object]) -> pd.DataFrame:
        df = self.conn.execute(sql, params).df()
        df.columns = [str(c).strip().strip('"').strip("'") for c in df.columns]
        return df
