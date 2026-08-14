"""Phát hiện lệch baseline lịch sử cho FR-302."""

from __future__ import annotations

import numpy as np
import pandas as pd

_PROFILE_KEYS = ["ne_id", "cell_id", "kpi_name", "temporal_profile"]
_DAY_TYPE_KEYS = _PROFILE_KEYS + ["day_type"]


class HistoricalBaselineDetector:
    """Gắn cờ khi trung bình sau tác động lệch baseline lịch sử từ 2 sigma trở lên."""

    def __init__(self, *, z_threshold: float = 2.0) -> None:
        if z_threshold <= 0:
            raise ValueError("z_threshold phải > 0")
        self.z_threshold = float(z_threshold)

    def detect(self, report_df: pd.DataFrame, baseline_df: pd.DataFrame) -> pd.DataFrame:
        required_report = set(_PROFILE_KEYS + ["post_mean"])
        missing_report = sorted(required_report.difference(report_df.columns))
        if missing_report:
            raise ValueError(
                f"Impact report thiếu cột cho baseline detector: {', '.join(missing_report)}"
            )

        use_day_type = "day_type" in report_df.columns and "day_type" in baseline_df.columns
        keys = _DAY_TYPE_KEYS if use_day_type else _PROFILE_KEYS
        required_baseline = set(keys + ["mean", "std"])
        missing_baseline = sorted(required_baseline.difference(baseline_df.columns))
        if missing_baseline:
            raise ValueError(
                f"Baseline lịch sử thiếu cột: {', '.join(missing_baseline)}"
            )

        baseline_columns = keys + ["sample_count", "mean", "std", "p05", "p95"]
        available = [column for column in baseline_columns if column in baseline_df.columns]
        selected = baseline_df[available].copy()
        rename = {
            column: f"historical_{column}"
            for column in available
            if column not in keys
        }
        selected = selected.rename(columns=rename)

        result = report_df.merge(selected, how="left", on=keys, validate="many_to_one")
        mean = pd.to_numeric(result["historical_mean"], errors="coerce")
        std = pd.to_numeric(result["historical_std"], errors="coerce")
        post_mean = pd.to_numeric(result["post_mean"], errors="coerce")
        valid = mean.notna() & std.notna() & post_mean.notna() & (std > 0)

        z_score = pd.Series(np.nan, index=result.index, dtype=float)
        z_score.loc[valid] = (
            (post_mean.loc[valid] - mean.loc[valid]).abs() / std.loc[valid]
        )
        result["historical_z_score"] = z_score
        result["baseline_abnormal"] = (z_score >= self.z_threshold).fillna(False)
        result["baseline_z_threshold"] = self.z_threshold
        return result
