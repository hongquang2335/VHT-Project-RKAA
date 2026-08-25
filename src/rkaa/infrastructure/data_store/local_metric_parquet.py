"""Local Parquet store for large read-only analytical snapshots.

MinIO remains the source of truth. This adapter only stores snapshots queried
from MinIO so long historical ranges can be reused without duplicating them in
SQLite.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


class LocalMetricParquetStore:
    """Write/query chunked long-format KPI/Counter snapshots with DuckDB."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def write_chunk(
        self,
        df: pd.DataFrame,
        *,
        start_time: pd.Timestamp,
        end_time: pd.Timestamp,
        overwrite: bool = False,
    ) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        name = (
            f"part-{start_time.strftime('%Y%m%dT%H%M%S')}"
            f"-{end_time.strftime('%Y%m%dT%H%M%S')}.parquet"
        )
        path = self.root / name
        if path.exists() and not overwrite:
            return path

        working = df.copy()
        for column in ("timestamp", "period_end"):
            if column in working.columns:
                working[column] = pd.to_datetime(working[column], errors="coerce")

        import duckdb

        conn = duckdb.connect()
        try:
            conn.register("metric_chunk", working)
            escaped_path = str(path.resolve()).replace("'", "''")
            conn.execute(
                f"COPY metric_chunk TO '{escaped_path}' "
                "(FORMAT PARQUET, COMPRESSION ZSTD)"
            )
        finally:
            conn.close()
        return path

    def parquet_files(self) -> list[Path]:
        if not self.root.exists():
            return []
        return sorted(self.root.glob("*.parquet"))

    def query(
        self,
        *,
        start_time: str | None = None,
        end_time: str | None = None,
        ne_ids: list[str] | None = None,
        cell_ids: list[str] | None = None,
        metric_names: list[str] | None = None,
        metric_kind: str = "all",
        limit: int | None = None,
    ) -> tuple[pd.DataFrame, int]:
        files = self.parquet_files()
        if not files:
            raise FileNotFoundError(f"Không tìm thấy Parquet trong {self.root}")
        if metric_kind not in {"all", "kpi", "counter"}:
            raise ValueError("metric_kind phải là all, kpi hoặc counter")
        if limit is not None and limit <= 0:
            raise ValueError("limit phải > 0")

        glob_path = str((self.root / "*.parquet").resolve()).replace("'", "''")
        source = f"read_parquet('{glob_path}', union_by_name=true)"
        clauses: list[str] = []
        params: list[object] = []

        if start_time is not None:
            clauses.append("timestamp >= CAST(? AS TIMESTAMP)")
            params.append(start_time)
        if end_time is not None:
            clauses.append("timestamp < CAST(? AS TIMESTAMP)")
            params.append(end_time)

        def add_in_filter(column: str, values: list[str] | None) -> None:
            normalized = [value.strip() for value in (values or []) if value.strip()]
            if not normalized:
                return
            placeholders = ", ".join("?" for _ in normalized)
            clauses.append(f'"{column}" IN ({placeholders})')
            params.extend(normalized)

        add_in_filter("ne_id", ne_ids)
        add_in_filter("cell_id", cell_ids)
        add_in_filter("kpi_name", metric_names)

        if metric_kind == "kpi":
            clauses.append("COALESCE(is_counter, false) = false")
        elif metric_kind == "counter":
            clauses.append("COALESCE(is_counter, false) = true")

        where = "" if not clauses else " WHERE " + " AND ".join(clauses)
        count_sql = f"SELECT COUNT(*) FROM {source}{where}"
        data_sql = f"SELECT * FROM {source}{where} ORDER BY timestamp, ne_id, cell_id, kpi_name"
        if limit is not None:
            data_sql += f" LIMIT {int(limit)}"

        import duckdb

        conn = duckdb.connect()
        try:
            count = int(conn.execute(count_sql, params).fetchone()[0])
            df = conn.execute(data_sql, params).df()
        finally:
            conn.close()
        return df, count
