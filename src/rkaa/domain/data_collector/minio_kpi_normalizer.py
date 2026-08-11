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


DEFAULT_KPI_MAPPING: list[KPIMappingItem] = [
    KPIMappingItem(
        source_column="ENDC SSR VTNET (%)",
        canonical_name="ENDC_SSR",
        unit="%",
        direction_preference="higher_is_better",
    ),
    KPIMappingItem(
        source_column="ENDC CDR VTNET (%)",
        canonical_name="ENDC_CDR",
        unit="%",
        direction_preference="lower_is_better",
    ),
    KPIMappingItem(
        source_column="NR RASR VTNET (%)",
        canonical_name="NR_RASR",
        unit="%",
        direction_preference="higher_is_better",
    ),
    KPIMappingItem(
        source_column="PSCell Change Intra-SgNB SR VTNET (%)",
        canonical_name="PSCELL_CHANGE_INTRA_SGNB_SR",
        unit="%",
        direction_preference="higher_is_better",
    ),
    KPIMappingItem(
        source_column="PSCell Change Inter-SgNB SR VTNET (%)",
        canonical_name="PSCELL_CHANGE_INTER_SGNB_SR",
        unit="%",
        direction_preference="higher_is_better",
    ),
    KPIMappingItem(
        source_column="Max RRC Connected NR ENDC User (UE)",
        canonical_name="MAX_RRC_CONNECTED_NR_ENDC_USER",
        unit="UE",
        direction_preference="informational",
    ),
    KPIMappingItem(
        source_column="NSA PS Traffic (GBytes)",
        canonical_name="NSA_PS_TRAFFIC",
        unit="GBytes",
        direction_preference="informational",
    ),
]


class MinioKPINormalizer:
    """Chuẩn hóa dữ liệu wide MinIO thành long-format theo NE + Cell + KPI."""

    def __init__(
        self,
        *,
        datetime_col: str = "datetime",
        ne_col: str = "ne",
        cellname_col: str = "cellname",
        granularity_minutes: int = 15,
        kpi_mapping: list[KPIMappingItem] | None = None,
    ) -> None:
        self.datetime_col = datetime_col
        self.ne_col = ne_col
        self.cellname_col = cellname_col
        self.granularity_minutes = granularity_minutes
        self.kpi_mapping = kpi_mapping or DEFAULT_KPI_MAPPING

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
                    # FR-201 cần nhìn thấy null để ghi nhận và loại có lý do.
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
            ],
        )
