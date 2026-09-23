from __future__ import annotations

from pathlib import Path

import pandas as pd

from rkaa.domain.data_collector.station_selection import normalize_station_ids


class CSVKPIAdapter:
    """Read-only adapter for wide KPI/counter CSV files.

    The adapter only knows source-schema concerns (where time/NE/cell live).
    KPI semantics are intentionally kept outside this class and supplied by
    configuration to the normalizer.
    """

    def __init__(
        self,
        csv_path: str | Path,
        *,
        dayfirst: bool = False,
        encoding: str = "utf-8-sig",
        delimiter: str = ",",
    ) -> None:
        self.csv_path = Path(csv_path)
        self.dayfirst = dayfirst
        self.encoding = encoding
        self.delimiter = delimiter
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Không tìm thấy CSV: {self.csv_path}")

    def available_columns(self) -> list[str]:
        header = pd.read_csv(
            self.csv_path,
            nrows=0,
            encoding=self.encoding,
            sep=self.delimiter,
        )
        return [self._clean_column_name(column) for column in header.columns]

    def fetch_kpi_wide_dataframe(
        self,
        *,
        selected_columns: list[str],
        datetime_col: str,
        ne_col: str,
        cellname_col: str,
        start_time: str | None = None,
        end_time: str | None = None,
        cellname: str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        return self._read_filtered(
            selected_columns=selected_columns,
            datetime_col=datetime_col,
            ne_col=ne_col,
            cellname_col=cellname_col,
            start_time=start_time,
            end_time=end_time,
            cellname=cellname,
            station_ids=None,
            limit=limit,
        )

    def fetch_kpi_wide_dataframe_for_stations(
        self,
        *,
        station_ids: list[str],
        selected_columns: list[str],
        datetime_col: str,
        ne_col: str,
        cellname_col: str,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        normalized_station_ids = normalize_station_ids(station_ids)
        if not normalized_station_ids:
            return pd.DataFrame(columns=selected_columns)

        return self._read_filtered(
            selected_columns=selected_columns,
            datetime_col=datetime_col,
            ne_col=ne_col,
            cellname_col=cellname_col,
            start_time=start_time,
            end_time=end_time,
            cellname=None,
            station_ids=normalized_station_ids,
            limit=limit,
        )

    def _read_filtered(
        self,
        *,
        selected_columns: list[str],
        datetime_col: str,
        ne_col: str,
        cellname_col: str,
        start_time: str | None,
        end_time: str | None,
        cellname: str | None,
        station_ids: list[str] | None,
        limit: int | None,
    ) -> pd.DataFrame:
        if limit is not None and limit <= 0:
            raise ValueError("limit must be greater than zero")
        if cellname and station_ids:
            raise ValueError("Chỉ dùng cellname hoặc station_ids, không dùng đồng thời")

        requested = self._unique_preserving_order(
            [datetime_col, ne_col, cellname_col, *selected_columns]
        )
        available = set(self.available_columns())
        missing = [column for column in requested if column not in available]
        if missing:
            raise KeyError(
                "CSV thiếu cột được adapter yêu cầu: "
                f"{missing}. Cột hiện có: {sorted(available)}"
            )

        df = pd.read_csv(
            self.csv_path,
            usecols=requested,
            encoding=self.encoding,
            sep=self.delimiter,
        )
        df.columns = [self._clean_column_name(column) for column in df.columns]
        parsed_time = pd.to_datetime(
            df[datetime_col],
            errors="coerce",
            dayfirst=self.dayfirst,
        )
        df[datetime_col] = parsed_time
        df = df.loc[parsed_time.notna()].copy()

        if start_time is not None:
            start = self._parse_boundary(start_time)
            df = df.loc[df[datetime_col] >= start]
        if end_time is not None:
            end = self._parse_boundary(end_time)
            df = df.loc[df[datetime_col] < end]
        if cellname is not None:
            df = df.loc[df[cellname_col].astype(str).str.strip() == str(cellname).strip()]
        if station_ids:
            station_set = set(normalize_station_ids(station_ids))
            df = df.loc[df[ne_col].astype(str).str.strip().isin(station_set)]
        if limit is not None:
            df = df.head(limit)

        return df.reset_index(drop=True)

    def _parse_boundary(self, value: str) -> pd.Timestamp:
        # ISO CLI arguments are unambiguous and should not inherit dayfirst.
        try:
            return pd.Timestamp(value)
        except (TypeError, ValueError):
            return pd.to_datetime(value, errors="raise", dayfirst=self.dayfirst)

    @staticmethod
    def _clean_column_name(value: object) -> str:
        return str(value).strip().strip('"').strip("'")

    @staticmethod
    def _unique_preserving_order(values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value not in seen:
                result.append(value)
                seen.add(value)
        return result
