"""Kiểm tra counter/KPI âm hoặc vượt miền thiết kế cấu hình."""

from __future__ import annotations

import pandas as pd

from rkaa.domain.data_quality.models import DataQualityIssue, RangeValidationConfig


class RangeValidator:
    def __init__(self, config: RangeValidationConfig) -> None:
        self.config = config

    def detect(self, df: pd.DataFrame) -> list[DataQualityIssue]:
        if not self.config.enabled or not self.config.rules:
            return []

        issues: list[DataQualityIssue] = []
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
                if reason is None:
                    continue
                issues.append(
                    DataQualityIssue(
                        issue_type="INVALID_RANGE",
                        severity="ERROR",
                        row_index=int(row["_dq_row_id"]),
                        ne_id=str(row["ne_id"]),
                        cell_id=str(row["cell_id"]),
                        kpi_name=str(row["kpi_name"]),
                        timestamp=row["timestamp"],
                        period_end=row["period_end"],
                        value=value,
                        detail=reason,
                    )
                )
        return issues
