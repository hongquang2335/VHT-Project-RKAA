"""Phát hiện duplicate exact và duplicate xung đột của FR-203."""

from __future__ import annotations

import math

import pandas as pd

from rkaa.domain.data_quality.models import DataQualityIssue, DuplicateConfig


class DuplicateDetector:
    # KPI long-format cần cả cell_id và period_end để không nhầm hai cell/timeslot.
    KEY_COLUMNS = ["timestamp", "period_end", "ne_id", "cell_id", "kpi_name"]

    def __init__(self, config: DuplicateConfig) -> None:
        self.config = config

    @staticmethod
    def _same_value(left: object, right: object) -> bool:
        try:
            if pd.isna(left) and pd.isna(right):
                return True
        except (TypeError, ValueError):
            pass
        if isinstance(left, float) and isinstance(right, float):
            return math.isclose(left, right, rel_tol=0.0, abs_tol=0.0)
        return left == right

    def detect(
        self,
        df: pd.DataFrame,
    ) -> tuple[pd.DataFrame, list[DataQualityIssue]]:
        if not self.config.enabled or df.empty:
            return df.copy(), []

        working = df.copy()
        drop_indexes: list[int] = []
        issues: list[DataQualityIssue] = []

        grouped = working.groupby(self.KEY_COLUMNS, dropna=False, sort=False)
        for _, group in grouped:
            if len(group) <= 1:
                continue

            first_value = group.iloc[0]["value"]
            exact = all(
                self._same_value(first_value, value)
                for value in group["value"].iloc[1:]
            )

            if exact:
                for idx in group.index[1:]:
                    row = working.loc[idx]
                    drop_indexes.append(int(idx))
                    issues.append(
                        DataQualityIssue(
                            issue_type="DUPLICATE_EXACT",
                            severity="INFO",
                            row_index=int(row["_dq_row_id"]),
                            ne_id=str(row["ne_id"]),
                            cell_id=str(row["cell_id"]),
                            kpi_name=str(row["kpi_name"]),
                            timestamp=row["timestamp"],
                            period_end=row["period_end"],
                            value=row["value"],
                            detail="bản ghi duplicate exact; giữ record xuất hiện đầu tiên",
                        )
                    )
            else:
                values = group["value"].tolist()
                for _, row in group.iterrows():
                    issues.append(
                        DataQualityIssue(
                            issue_type="DUPLICATE_CONFLICT",
                            severity="ERROR",
                            row_index=int(row["_dq_row_id"]),
                            ne_id=str(row["ne_id"]),
                            cell_id=str(row["cell_id"]),
                            kpi_name=str(row["kpi_name"]),
                            timestamp=row["timestamp"],
                            period_end=row["period_end"],
                            value=row["value"],
                            detail=f"cùng key nhưng value khác nhau: {values}",
                        )
                    )

        if drop_indexes:
            working = working.drop(index=drop_indexes).reset_index(drop=True)
        return working, issues
