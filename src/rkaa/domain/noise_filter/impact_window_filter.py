"""Bước 2 FR-201: loại dữ liệu trong maintenance/impact window."""

from __future__ import annotations

import pandas as pd

from rkaa.domain.noise_filter.models import (
    ExclusionWindow,
    FilterOutcome,
    ImpactWindowConfig,
)
from rkaa.domain.noise_filter.utils import parse_timestamp_series, require_columns, split_by_mask


class ImpactWindowFilter:
    def __init__(
        self,
        config: ImpactWindowConfig,
        windows: list[ExclusionWindow] | None = None,
    ) -> None:
        self.config = config
        self.windows = list(windows or [])

    def _match_ne(self, series: pd.Series, ne_id: str) -> pd.Series:
        """Khớp NE theo mã NE thực tế; không suy NE từ prefix cell_id."""
        values = series.astype(str)
        if self.config.match_mode in {"exact", "exact_or_prefix"}:
            # exact_or_prefix được giữ để tương thích config cũ, nhưng schema mới
            # đã có ne_id riêng nên phép khớp đúng là exact.
            return values == ne_id
        raise ValueError(f"match_mode không hỗ trợ: {self.config.match_mode}")

    @staticmethod
    def _match_cell(series: pd.Series, cell_id: str | None) -> pd.Series:
        """cell_id=None áp dụng window cho toàn NE; có cell_id thì khớp chính xác."""
        if cell_id is None:
            return pd.Series(True, index=series.index)
        return series.astype(str) == cell_id

    def apply(self, df: pd.DataFrame) -> FilterOutcome:
        require_columns(df, ("timestamp", "ne_id", "cell_id"))
        if not self.windows:
            return FilterOutcome(
                cleaned_df=df.copy(),
                excluded_df=pd.DataFrame(
                    columns=[*df.columns.tolist(), "filter_stage", "filter_reason", "detail"]
                ),
                summary={"status": "SKIPPED_NO_WINDOWS", "excluded": 0, "windows": 0},
            )

        timestamps = parse_timestamp_series(df["timestamp"])
        mask = pd.Series(False, index=df.index)
        reasons = pd.Series("", index=df.index, dtype="object")
        details = pd.Series("", index=df.index, dtype="object")

        allowed_types = set(self.config.excluded_impact_types)
        applied_windows = 0

        for window in self.windows:
            if allowed_types and window.reason not in allowed_types:
                continue

            t1 = pd.Timestamp(window.t1_utc)
            if t1.tzinfo is None:
                t1 = t1.tz_localize("UTC")
            else:
                t1 = t1.tz_convert("UTC")

            ne_mask = self._match_ne(df["ne_id"], window.ne_id)
            cell_mask = self._match_cell(df["cell_id"], window.cell_id)
            time_mask = timestamps >= t1

            if window.t2_utc is not None:
                t2 = pd.Timestamp(window.t2_utc)
                if t2.tzinfo is None:
                    t2 = t2.tz_localize("UTC")
                else:
                    t2 = t2.tz_convert("UTC")
                time_mask &= timestamps < t2

            current = ne_mask & cell_mask & time_mask
            new_rows = current & ~mask
            reasons.loc[new_rows] = window.reason
            details.loc[new_rows] = (
                f"source={window.source}; ne_id={window.ne_id}; "
                f"cell_id={window.cell_id or 'ALL'}; "
                f"t1={window.t1_utc.isoformat()}; "
                f"t2={window.t2_utc.isoformat() if window.t2_utc else 'ONGOING'}"
            )
            mask |= current
            applied_windows += 1

        cleaned, excluded = split_by_mask(
            df,
            mask,
            stage="IMPACT_WINDOW",
            reasons=reasons,
            details=details,
        )
        return FilterOutcome(
            cleaned_df=cleaned,
            excluded_df=excluded,
            summary={
                "status": "ENABLED",
                "excluded": int(mask.sum()),
                "windows": applied_windows,
            },
        )
