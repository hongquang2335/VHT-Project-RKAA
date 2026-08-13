"""Gán profile ngày/đêm và tạo dữ liệu profile cho FR-401."""

from __future__ import annotations

import pandas as pd

from rkaa.domain.temporal_analyzer.models import (
    TemporalAnalysisResult,
    TemporalProfileConfig,
)

_REQUIRED_COLUMNS = {
    "timestamp",
    "period_end",
    "ne_id",
    "cell_id",
    "kpi_name",
    "value",
}


class TemporalAnalyzer:
    """Phân loại từng data point theo BUSY/OFF_PEAK/TRANSITION."""

    def __init__(self, config: TemporalProfileConfig) -> None:
        self.config = config

    def classify_period(self, minute_of_day: int) -> str:
        matches = [
            window.profile.value
            for window in self.config.windows
            if window.contains(minute_of_day)
        ]
        if len(matches) != 1:
            raise ValueError(
                "Cấu hình temporal profile phải khớp đúng 1 profile cho mỗi phút; "
                f"minute_of_day={minute_of_day}, matches={matches}"
            )
        return matches[0]

    def analyze(self, df: pd.DataFrame) -> TemporalAnalysisResult:
        missing = sorted(_REQUIRED_COLUMNS.difference(df.columns))
        if missing:
            raise ValueError(f"Thiếu cột bắt buộc cho FR-401: {', '.join(missing)}")

        working = df.copy()
        timestamps = pd.to_datetime(
            working["timestamp"],
            errors="coerce",
            utc=True,
            format="mixed",
        )
        if timestamps.isna().any():
            bad = int(timestamps.isna().sum())
            raise ValueError(
                f"FR-401 nhận {bad} timestamp không hợp lệ; hãy chạy FR-203 trước"
            )

        values = pd.to_numeric(working["value"], errors="coerce")
        if values.isna().any():
            bad = int(values.isna().sum())
            raise ValueError(
                f"FR-401 nhận {bad} value không phải số; hãy chạy FR-203/FR-201 trước"
            )

        working["timestamp"] = timestamps
        working["value"] = values.astype(float)
        local_timestamp = timestamps.dt.tz_convert(self.config.timezone)
        minute_of_day = local_timestamp.dt.hour * 60 + local_timestamp.dt.minute

        working["local_timestamp"] = local_timestamp
        working["profile_timezone"] = self.config.timezone
        working["minute_of_day"] = minute_of_day.astype(int)
        working["time_of_day"] = local_timestamp.dt.strftime("%H:%M")
        working["temporal_profile"] = working["minute_of_day"].map(
            self.classify_period
        )

        overlay = self.get_profile(working)
        return TemporalAnalysisResult(
            profiled_df=working.reset_index(drop=True),
            overlay_df=overlay,
        )

    @staticmethod
    def get_profile(profiled_df: pd.DataFrame) -> pd.DataFrame:
        """Tạo dữ liệu overlay profile theo cùng giờ trong ngày qua nhiều ngày."""

        group_columns = [
            "ne_id",
            "cell_id",
            "kpi_name",
            "temporal_profile",
            "minute_of_day",
            "time_of_day",
        ]
        if "unit" in profiled_df.columns:
            group_columns.append("unit")

        grouped = profiled_df.groupby(group_columns, dropna=False, sort=True)["value"]
        overlay = grouped.agg(
            sample_count="count",
            mean="mean",
            median="median",
            p05=lambda values: values.quantile(0.05),
            p95=lambda values: values.quantile(0.95),
        )
        return overlay.reset_index()
