"""Xác định cặp NE + Cell hợp lệ trước khi chạy phân tích FR-4xx."""

from __future__ import annotations

import math

import pandas as pd


_REQUIRED = {"timestamp", "ne_id", "cell_id"}


class ValidNECellSelector:
    """Đánh giá tính đủ dữ liệu ở cấp cặp NE + Cell, không tune theo từng cell."""

    def __init__(
        self,
        *,
        granularity_minutes: int,
        minimum_clean_days: int = 14,
        minimum_completeness: float = 0.70,
    ) -> None:
        if granularity_minutes <= 0:
            raise ValueError("granularity_minutes phải > 0")
        if minimum_clean_days < 1:
            raise ValueError("minimum_clean_days phải >= 1")
        if not 0 < minimum_completeness <= 1:
            raise ValueError("minimum_completeness phải nằm trong (0, 1]")
        self.granularity_minutes = granularity_minutes
        self.minimum_clean_days = minimum_clean_days
        self.minimum_completeness = minimum_completeness

    def evaluate(self, df: pd.DataFrame) -> pd.DataFrame:
        missing = sorted(_REQUIRED.difference(df.columns))
        if missing:
            raise ValueError(f"Thiếu cột để xác định valid NE-Cell: {', '.join(missing)}")

        selected_columns = ["timestamp", "ne_id", "cell_id"]
        if "value" in df.columns:
            selected_columns.append("value")
        working = df[selected_columns].copy()
        working["timestamp"] = pd.to_datetime(
            working["timestamp"], errors="coerce", utc=True, format="mixed"
        )
        working["ne_id"] = working["ne_id"].astype("string").fillna("").str.strip()
        working["cell_id"] = working["cell_id"].astype("string").fillna("").str.strip()
        working = working.dropna(subset=["timestamp"])
        if "value" in working.columns:
            working["_usable_value"] = pd.to_numeric(
                working["value"], errors="coerce"
            ).notna()
        else:
            working["_usable_value"] = True

        rows: list[dict[str, object]] = []
        for (ne_id, cell_id), group in working.groupby(
            ["ne_id", "cell_id"], dropna=False, sort=True
        ):
            timestamps = group["timestamp"].drop_duplicates().sort_values()
            nonempty_id = bool(ne_id) and bool(cell_id)
            if timestamps.empty:
                observed_periods = 0
                expected_periods = 0
                clean_day_count = 0
                completeness = 0.0
            else:
                observed_periods = int(len(timestamps))
                span_minutes = (timestamps.iloc[-1] - timestamps.iloc[0]).total_seconds() / 60
                expected_periods = int(math.floor(span_minutes / self.granularity_minutes)) + 1
                clean_day_count = int(timestamps.dt.strftime("%Y-%m-%d").nunique())
                completeness = (
                    observed_periods / expected_periods if expected_periods > 0 else 0.0
                )

            usable_value_count = int(group["_usable_value"].sum())
            reasons: list[str] = []
            if not nonempty_id:
                reasons.append("EMPTY_NE_OR_CELL")
            if usable_value_count == 0:
                reasons.append("NO_USABLE_KPI_VALUES")
            if clean_day_count < self.minimum_clean_days:
                reasons.append("INSUFFICIENT_DAYS")
            if completeness < self.minimum_completeness:
                reasons.append("LOW_COMPLETENESS")
            rows.append(
                {
                    "ne_id": str(ne_id),
                    "cell_id": str(cell_id),
                    "observed_periods": observed_periods,
                    "expected_periods": expected_periods,
                    "clean_day_count": clean_day_count,
                    "completeness": completeness,
                    "usable_value_count": usable_value_count,
                    "is_valid_pair": not reasons,
                    "invalid_reason": ";".join(reasons),
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def filter_valid(df: pd.DataFrame, validity_df: pd.DataFrame) -> pd.DataFrame:
        required = {"ne_id", "cell_id", "is_valid_pair"}
        missing = sorted(required.difference(validity_df.columns))
        if missing:
            raise ValueError(f"pair validity thiếu cột: {', '.join(missing)}")
        valid = validity_df.loc[
            validity_df["is_valid_pair"].astype(bool), ["ne_id", "cell_id"]
        ]
        if valid.empty:
            return df.iloc[0:0].copy()
        return df.merge(valid, how="inner", on=["ne_id", "cell_id"], validate="many_to_one")
