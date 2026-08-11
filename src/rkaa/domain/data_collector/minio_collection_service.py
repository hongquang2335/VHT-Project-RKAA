from __future__ import annotations

import pandas as pd

from rkaa.domain.data_collector.minio_kpi_adapter import MinioKPIAdapter
from rkaa.domain.data_collector.minio_kpi_normalizer import MinioKPINormalizer
from rkaa.domain.data_collector.station_selection import normalize_station_ids


class MinioCollectionService:
    def __init__(
        self,
        *,
        adapter: MinioKPIAdapter,
        normalizer: MinioKPINormalizer,
    ) -> None:
        self.adapter = adapter
        self.normalizer = normalizer

    def _empty_long_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(
            columns=[
                "timestamp",
                "period_end",
                "ne_id",
                "cell_id",
                "kpi_name",
                "value",
                "unit",
                "quality_flag",
            ]
        )

    def collect_once(
        self,
        *,
        start_time: str,
        end_time: str,
        cellname: str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        selected_columns = self.normalizer.required_columns()

        wide_df = self.adapter.fetch_kpi_wide_dataframe(
            selected_columns=selected_columns,
            datetime_col=self.normalizer.datetime_col,
            ne_col=self.normalizer.ne_col,
            cellname_col=self.normalizer.cellname_col,
            start_time=start_time,
            end_time=end_time,
            cellname=cellname,
            limit=limit,
        )

        if wide_df.empty:
            return self._empty_long_dataframe()

        return self.normalizer.normalize(wide_df)

    def collect_for_stations(
        self,
        *,
        start_time: str,
        end_time: str,
        station_ids: list[str],
        limit: int | None = None,
    ) -> pd.DataFrame:
        """Thu thập chỉ dữ liệu thuộc danh sách NE/trạm mong muốn."""
        normalized_station_ids = normalize_station_ids(station_ids)
        if not normalized_station_ids:
            return self._empty_long_dataframe()

        selected_columns = self.normalizer.required_columns()
        wide_df = self.adapter.fetch_kpi_wide_dataframe_for_stations(
            station_ids=normalized_station_ids,
            selected_columns=selected_columns,
            datetime_col=self.normalizer.datetime_col,
            ne_col=self.normalizer.ne_col,
            cellname_col=self.normalizer.cellname_col,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

        if wide_df.empty:
            return self._empty_long_dataframe()

        return self.normalizer.normalize(wide_df)
