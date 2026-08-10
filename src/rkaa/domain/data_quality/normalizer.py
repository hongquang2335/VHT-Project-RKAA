"""Chuẩn hóa schema/type đầu vào trước các kiểm tra FR-203."""

from __future__ import annotations

import pandas as pd

from rkaa.domain.data_quality.models import DataQualityIssue, NormalizationConfig


_REQUIRED_COLUMNS = ("timestamp", "ne_id", "kpi_name", "value")


class DataQualityNormalizer:
    def __init__(self, config: NormalizationConfig) -> None:
        self.config = config

    def normalize(self, df: pd.DataFrame) -> tuple[pd.DataFrame, list[DataQualityIssue]]:
        missing = [column for column in _REQUIRED_COLUMNS if column not in df.columns]
        if missing:
            raise ValueError(f"FR-203 thiếu cột bắt buộc: {missing}")

        working = df.copy()
        working["_dq_row_id"] = range(len(working))
        issues: list[DataQualityIssue] = []

        for column in ("ne_id", "kpi_name", "unit", "quality_flag"):
            if column in working.columns:
                working[column] = working[column].astype("string").str.strip()

        original_timestamp = working["timestamp"].copy()
        parsed_timestamp = pd.to_datetime(
            original_timestamp,
            errors="coerce",
            utc=True,
        )
        invalid_timestamp = parsed_timestamp.isna() & original_timestamp.notna()
        for idx in working.index[invalid_timestamp]:
            issues.append(
                DataQualityIssue(
                    issue_type="INVALID_TIMESTAMP",
                    severity="ERROR",
                    row_index=int(working.at[idx, "_dq_row_id"]),
                    ne_id=str(working.at[idx, "ne_id"]),
                    kpi_name=str(working.at[idx, "kpi_name"]),
                    timestamp=original_timestamp.at[idx],
                    value=working.at[idx, "value"],
                    detail="timestamp không parse được",
                )
            )
        working["timestamp"] = parsed_timestamp

        if "period_end" in working.columns:
            working["period_end"] = pd.to_datetime(
                working["period_end"],
                errors="coerce",
                utc=True,
            )

        original_value = working["value"].copy()
        numeric_value = pd.to_numeric(original_value, errors="coerce")
        non_numeric = original_value.notna() & numeric_value.isna()
        for idx in working.index[non_numeric]:
            issues.append(
                DataQualityIssue(
                    issue_type="NON_NUMERIC_VALUE",
                    severity="ERROR",
                    row_index=int(working.at[idx, "_dq_row_id"]),
                    ne_id=str(working.at[idx, "ne_id"]),
                    kpi_name=str(working.at[idx, "kpi_name"]),
                    timestamp=working.at[idx, "timestamp"],
                    value=original_value.at[idx],
                    detail="value không chuyển được sang số",
                )
            )
        working["value"] = numeric_value

        working = working.sort_values(
            ["ne_id", "kpi_name", "timestamp", "_dq_row_id"],
            na_position="last",
            kind="stable",
        ).reset_index(drop=True)
        return working, issues
