from __future__ import annotations
import sqlite3
import pandas as pd


class KPIRecordRepository:
    """Khung repository dự phòng cho bước lưu dữ liệu của FR-101."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def save_dataframe(self, dataframe: pd.DataFrame) -> int:
        dataframe.to_sql("kpi_record", self.connection, if_exists="append", index=False)
        return len(dataframe)
