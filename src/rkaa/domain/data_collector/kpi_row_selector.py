"""Tách record KPI và counter khi file long-format chứa cả hai loại metric."""

from __future__ import annotations

import pandas as pd


_TRUE_VALUES = {"1", "true", "yes", "y"}
_FALSE_VALUES = {"0", "false", "no", "n", "", "<na>", "nan", "none"}


def _counter_mask(df: pd.DataFrame) -> pd.Series:
    """Trả mask ``is_counter`` đã validate, hỗ trợ CSV bool/string.

    File legacy chưa có ``is_counter`` được xem là chỉ chứa KPI.
    """

    if "is_counter" not in df.columns:
        return pd.Series(False, index=df.index, dtype=bool)

    raw = df["is_counter"]
    if pd.api.types.is_bool_dtype(raw.dtype):
        return raw.fillna(False).astype(bool)

    normalized = raw.astype("string").str.strip().str.lower().fillna("")
    unknown = ~normalized.isin(_TRUE_VALUES | _FALSE_VALUES)
    if unknown.any():
        bad_values = sorted(set(normalized[unknown].astype(str)))
        raise ValueError(f"is_counter có giá trị không hợp lệ: {bad_values}")
    return normalized.isin(_TRUE_VALUES)


def split_metric_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Tách thành ``(kpi_df, counter_df)`` mà không thay đổi dữ liệu gốc."""

    counter_mask = _counter_mask(df)
    return df.loc[~counter_mask].copy(), df.loc[counter_mask].copy()


def select_kpi_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Giữ tương thích với các bước chỉ xử lý KPI như FR-201."""

    kpi_df, counter_df = split_metric_rows(df)
    return kpi_df, len(counter_df)
