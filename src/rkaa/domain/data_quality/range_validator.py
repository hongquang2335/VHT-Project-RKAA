"""Kiểm tra counter/KPI âm hoặc vượt miền thiết kế cấu hình."""

from __future__ import annotations

import pandas as pd

from rkaa.domain.data_quality.models import DataQualityIssue, RangeValidationConfig


class RangeValidator:
    def __init__(self, config: RangeValidationConfig) -> None:
        self.config = config

    @staticmethod
    def _issue(row: pd.Series, reason: str) -> DataQualityIssue:
        return DataQualityIssue(
            issue_type="INVALID_RANGE",
            severity="ERROR",
            row_index=int(row["_dq_row_id"]),
            ne_id=str(row["ne_id"]),
            cell_id=str(row["cell_id"]),
            kpi_name=str(row["kpi_name"]),
            timestamp=row["timestamp"],
            period_end=row["period_end"],
            value=row["value"],
            detail=reason,
        )

    def detect(self, df: pd.DataFrame) -> list[DataQualityIssue]:
        if not self.config.enabled:
            return []

        issues: list[DataQualityIssue] = []

        # KPI dùng rule theo tên KPI như trước đây.
        for kpi_name, rule in self.config.rules.items():
            kpi_rows = df[df["kpi_name"] == kpi_name]
            for _, row in kpi_rows.iterrows():
                value = row["value"]
                if pd.isna(value):
                    continue
                reason: str | None = None
                if rule.min_value is not None and value < rule.min_value:
                    reason = f"value={value} < min={rule.min_value}"
                elif rule.max_value is not None and value > rule.max_value:
                    reason = f"value={value} > max={rule.max_value}"
                if reason is not None:
                    issues.append(self._issue(row, reason))

        # FR-203 yêu cầu counter không hợp lệ (ví dụ giá trị âm). Pha 3 hiện
        # chỉ áp policy chung >= 0; chưa tự suy diễn behavior/reset/wrap.
        if self.config.counter_min_value is not None and "is_counter" in df.columns:
            counter_rows = df[df["is_counter"].fillna(False).astype(bool)]
            for _, row in counter_rows.iterrows():
                value = row["value"]
                if pd.isna(value) or value >= self.config.counter_min_value:
                    continue
                issues.append(
                    self._issue(
                        row,
                        (
                            f"counter value={value} < "
                            f"min={self.config.counter_min_value}"
                        ),
                    )
                )

        return issues
