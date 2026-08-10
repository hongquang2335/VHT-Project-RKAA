"""Tiện ích dùng chung cho các bộ lọc FR-201."""

from __future__ import annotations

import pandas as pd


EXCLUSION_COLUMNS = ["filter_stage", "filter_reason", "detail"]


def require_columns(df: pd.DataFrame, columns: tuple[str, ...]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Thiếu cột bắt buộc cho FR-201: {missing}")


def empty_excluded_like(df: pd.DataFrame) -> pd.DataFrame:
    columns = [*df.columns.tolist(), *EXCLUSION_COLUMNS]
    return pd.DataFrame(columns=columns)


def split_by_mask(
    df: pd.DataFrame,
    mask: pd.Series,
    *,
    stage: str,
    reasons: pd.Series | str,
    details: pd.Series | str = "",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Tách DataFrame theo mask và gắn metadata cho phần bị loại."""

    aligned_mask = mask.reindex(df.index, fill_value=False).astype(bool)
    cleaned = df.loc[~aligned_mask].copy()
    excluded = df.loc[aligned_mask].copy()

    if excluded.empty:
        return cleaned, empty_excluded_like(df)

    excluded["filter_stage"] = stage

    if isinstance(reasons, pd.Series):
        excluded["filter_reason"] = reasons.reindex(excluded.index).astype(str)
    else:
        excluded["filter_reason"] = reasons

    if isinstance(details, pd.Series):
        excluded["detail"] = details.reindex(excluded.index).fillna("").astype(str)
    else:
        excluded["detail"] = details

    return cleaned, excluded


def parse_timestamp_series(series: pd.Series) -> pd.Series:
    """Parse timestamp phục vụ so sánh nội bộ và coi timestamp naive là UTC."""

    parsed = pd.to_datetime(series, errors="coerce", utc=True)
    if parsed.isna().any():
        bad_count = int(parsed.isna().sum())
        raise ValueError(f"Có {bad_count} timestamp không parse được trong FR-201")
    return parsed
