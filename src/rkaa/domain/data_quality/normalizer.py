"""Chuẩn hóa schema/type đầu vào trước các kiểm tra FR-203."""

from __future__ import annotations

import pandas as pd

from rkaa.domain.data_quality.models import DataQualityIssue, NormalizationConfig


# Một record KPI long-format được định danh theo thời gian + NE + Cell + KPI.
_REQUIRED_COLUMNS = (
    "timestamp",
    "period_end",
    "ne_id",
    "cell_id",
    "kpi_name",
    "value",
)


_TRUE_COUNTER_VALUES = {"1", "true", "yes", "y"}
_FALSE_COUNTER_VALUES = {"0", "false", "no", "n", "", "<na>", "nan", "none"}


def _normalize_is_counter(series: pd.Series) -> pd.Series:
    """Chuẩn hóa cờ is_counter từ bool/string CSV về bool."""

    if pd.api.types.is_bool_dtype(series.dtype):
        return series.fillna(False).astype(bool)

    normalized = series.astype("string").str.strip().str.lower().fillna("")
    unknown = ~normalized.isin(_TRUE_COUNTER_VALUES | _FALSE_COUNTER_VALUES)
    if unknown.any():
        bad_values = sorted(set(normalized[unknown].astype(str)))
        raise ValueError(f"is_counter có giá trị không hợp lệ: {bad_values}")
    return normalized.isin(_TRUE_COUNTER_VALUES)


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

        for column in ("ne_id", "cell_id", "kpi_name", "unit", "quality_flag"):
            if column in working.columns:
                working[column] = working[column].astype("string").str.strip()

        if "is_counter" in working.columns:
            working["is_counter"] = _normalize_is_counter(working["is_counter"])

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
                    cell_id=str(working.at[idx, "cell_id"]),
                    kpi_name=str(working.at[idx, "kpi_name"]),
                    timestamp=original_timestamp.at[idx],
                    period_end=working.at[idx, "period_end"],
                    value=working.at[idx, "value"],
                    detail="timestamp không parse được",
                )
            )
        working["timestamp"] = parsed_timestamp

        original_period_end = working["period_end"].copy()
        parsed_period_end = pd.to_datetime(
            original_period_end,
            errors="coerce",
            utc=True,
        )
        invalid_period_end = parsed_period_end.isna() & original_period_end.notna()
        for idx in working.index[invalid_period_end]:
            issues.append(
                DataQualityIssue(
                    issue_type="INVALID_PERIOD_END",
                    severity="ERROR",
                    row_index=int(working.at[idx, "_dq_row_id"]),
                    ne_id=str(working.at[idx, "ne_id"]),
                    cell_id=str(working.at[idx, "cell_id"]),
                    kpi_name=str(working.at[idx, "kpi_name"]),
                    timestamp=working.at[idx, "timestamp"],
                    period_end=original_period_end.at[idx],
                    value=working.at[idx, "value"],
                    detail="period_end không parse được",
                )
            )
        working["period_end"] = parsed_period_end

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
                    cell_id=str(working.at[idx, "cell_id"]),
                    kpi_name=str(working.at[idx, "kpi_name"]),
                    timestamp=working.at[idx, "timestamp"],
                    period_end=working.at[idx, "period_end"],
                    value=original_value.at[idx],
                    detail="value không chuyển được sang số",
                )
            )
        working["value"] = numeric_value

        working = working.sort_values(
            ["ne_id", "cell_id", "kpi_name", "timestamp", "period_end", "_dq_row_id"],
            na_position="last",
            kind="stable",
        ).reset_index(drop=True)
        return working, issues
