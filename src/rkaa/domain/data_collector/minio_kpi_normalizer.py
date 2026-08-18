from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pandas as pd


@dataclass(frozen=True)
class KPIMappingItem:
    source_column: str
    canonical_name: str
    unit: str
    direction_preference: str
    is_counter: bool = False


class MinioKPINormalizer:
    """Chuẩn hóa dữ liệu wide MinIO thành long-format theo NE + Cell + KPI."""

    def __init__(
        self,
        *,
        kpi_mapping: list[KPIMappingItem],
        datetime_col: str = "datetime",
        ne_col: str = "ne",
        cellname_col: str = "cellname",
        granularity_minutes: int = 15,
    ) -> None:
        if not kpi_mapping:
            raise ValueError("kpi_mapping không được rỗng")

        self.datetime_col = datetime_col
        self.ne_col = ne_col
        self.cellname_col = cellname_col
        self.granularity_minutes = granularity_minutes
        self.kpi_mapping = list(kpi_mapping)

    def required_columns(self) -> list[str]:
        return [
            self.datetime_col,
            self.ne_col,
            self.cellname_col,
            *[item.source_column for item in self.kpi_mapping],
        ]

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.columns = [str(c).strip().strip('"').strip("'") for c in df.columns]

        for column, label in (
            (self.datetime_col, "thời gian"),
            (self.ne_col, "NE"),
            (self.cellname_col, "cell"),
        ):
            if column not in df.columns:
                raise KeyError(
                    f"Không tìm thấy cột {label} {column}. "
                    f"Cột hiện có: {df.columns.tolist()}"
                )

        df[self.datetime_col] = pd.to_datetime(df[self.datetime_col], errors="coerce")

        records: list[dict[str, object]] = []

        for _, row in df.iterrows():
            start_time = row[self.datetime_col]
            if pd.isna(start_time):
                continue

            period_end = start_time + timedelta(minutes=self.granularity_minutes)
            ne_id = str(row[self.ne_col]).strip()
            cell_id = str(row[self.cellname_col]).strip()

            for item in self.kpi_mapping:
                if item.source_column not in df.columns:
                    continue

                value = row[item.source_column]
                if pd.isna(value):
                    # FR-201 cần nhìn thấy null của KPI để ghi nhận và loại có lý do.
                    records.append(
                        {
                            "timestamp": start_time.isoformat(),
                            "period_end": period_end.isoformat(),
                            "ne_id": ne_id,
                            "cell_id": cell_id,
                            "kpi_name": item.canonical_name,
                            "value": float("nan"),
                            "unit": item.unit,
                            "quality_flag": "MISSING",
                            "is_counter": item.is_counter,
                        }
                    )
                    continue

                try:
                    numeric_value = float(value)
                except (ValueError, TypeError):
                    continue

                records.append(
                    {
                        "timestamp": start_time.isoformat(),
                        "period_end": period_end.isoformat(),
                        "ne_id": ne_id,
                        "cell_id": cell_id,
                        "kpi_name": item.canonical_name,
                        "value": numeric_value,
                        "unit": item.unit,
                        "quality_flag": "GOOD",
                        "is_counter": item.is_counter,
                    }
                )

        return pd.DataFrame(
            records,
            columns=[
                "timestamp",
                "period_end",
                "ne_id",
                "cell_id",
                "kpi_name",
                "value",
                "unit",
                "quality_flag",
                "is_counter",
            ],
        )
