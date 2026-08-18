"""Chọn các record KPI khi file thu thập có cả KPI và counter."""

from __future__ import annotations

import pandas as pd


_TRUE_VALUES = {"1", "true", "yes", "y"}
_FALSE_VALUES = {"0", "false", "no", "n", "", "<na>", "nan", "none"}


def select_kpi_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Loại counter khỏi đầu vào các bước xử lý KPI hiện tại.

    File legacy chưa có ``is_counter`` được xem là chỉ chứa KPI để giữ tương thích.
    """

    if "is_counter" not in df.columns:
        return df.copy(), 0

    raw = df["is_counter"]
    if pd.api.types.is_bool_dtype(raw.dtype):
        counter_mask = raw.fillna(False).astype(bool)
    else:
        normalized = raw.astype("string").str.strip().str.lower().fillna("")
        unknown = ~normalized.isin(_TRUE_VALUES | _FALSE_VALUES)
        if unknown.any():
            bad_values = sorted(set(normalized[unknown].astype(str)))
            raise ValueError(f"is_counter có giá trị không hợp lệ: {bad_values}")
        counter_mask = normalized.isin(_TRUE_VALUES)

    return df.loc[~counter_mask].copy(), int(counter_mask.sum())
