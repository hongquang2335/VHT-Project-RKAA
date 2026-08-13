"""Phân loại WEEKDAY/WEEKEND và tổng hợp profile cho FR-402."""

from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd

from rkaa.domain.temporal_analyzer.models import DayType, WeeklyCycleAnalysisResult

_REQUIRED_COLUMNS = {
    "timestamp",
    "ne_id",
    "cell_id",
    "kpi_name",
    "value",
    "temporal_profile",
}

_DAY_NAMES = {
    0: "MONDAY",
    1: "TUESDAY",
    2: "WEDNESDAY",
    3: "THURSDAY",
    4: "FRIDAY",
    5: "SATURDAY",
    6: "SUNDAY",
}


class WeeklyCycleAnalyzer:
    """Phân loại bản ghi KPI thành WEEKDAY/WEEKEND theo múi giờ profile FR-401."""

    @staticmethod
    def classify_day(weekday_index: int) -> str:
        if not 0 <= weekday_index <= 6:
            raise ValueError(f"weekday_index phải nằm trong [0, 6], nhận được {weekday_index}")
        return DayType.WEEKDAY.value if weekday_index <= 4 else DayType.WEEKEND.value

    @staticmethod
    def _resolve_timezone(df: pd.DataFrame) -> str:
        if "profile_timezone" not in df.columns:
            return "UTC"

        values = (
            df["profile_timezone"]
            .dropna()
            .astype(str)
            .str.strip()
        )
        unique = [value for value in values.unique().tolist() if value]
        if not unique:
            return "UTC"
        if len(unique) != 1:
            raise ValueError(
                "FR-402 yêu cầu input chỉ có một profile_timezone; "
                f"nhận được {sorted(unique)}"
            )
        try:
            ZoneInfo(unique[0])
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"profile_timezone không hợp lệ: {unique[0]}") from exc
        return unique[0]

    def analyze(self, df: pd.DataFrame) -> WeeklyCycleAnalysisResult:
        missing = sorted(_REQUIRED_COLUMNS.difference(df.columns))
        if missing:
            raise ValueError(f"Thiếu cột bắt buộc cho FR-402: {', '.join(missing)}")

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
                f"FR-402 nhận {bad} timestamp không hợp lệ; hãy chạy FR-203 trước"
            )

        values = pd.to_numeric(working["value"], errors="coerce")
        if values.isna().any():
            bad = int(values.isna().sum())
            raise ValueError(
                f"FR-402 nhận {bad} value không phải số; hãy chạy FR-203/FR-201 trước"
            )

        timezone = self._resolve_timezone(working)
        local_timestamp = timestamps.dt.tz_convert(timezone)
        weekday_index = local_timestamp.dt.dayofweek.astype(int)

        working["timestamp"] = timestamps
        working["value"] = values.astype(float)
        working["local_timestamp"] = local_timestamp
        working["profile_timezone"] = timezone
        working["calendar_date"] = local_timestamp.dt.strftime("%Y-%m-%d")
        working["weekday_index"] = weekday_index
        working["day_of_week"] = weekday_index.map(_DAY_NAMES)
        working["day_type"] = weekday_index.map(self.classify_day)

        if "minute_of_day" not in working.columns:
            working["minute_of_day"] = (
                local_timestamp.dt.hour * 60 + local_timestamp.dt.minute
            ).astype(int)
        if "time_of_day" not in working.columns:
            working["time_of_day"] = local_timestamp.dt.strftime("%H:%M")

        overlay = self.get_day_type_profile(working)
        return WeeklyCycleAnalysisResult(
            profiled_df=working.reset_index(drop=True),
            overlay_df=overlay,
        )

    @staticmethod
    def get_day_type_profile(profiled_df: pd.DataFrame) -> pd.DataFrame:
        """Gộp cùng thời điểm trong ngày riêng cho WEEKDAY và WEEKEND."""

        required = {
            "ne_id",
            "cell_id",
            "kpi_name",
            "temporal_profile",
            "day_type",
            "minute_of_day",
            "time_of_day",
            "value",
        }
        missing = sorted(required.difference(profiled_df.columns))
        if missing:
            raise ValueError(f"Thiếu cột để tạo overlay FR-402: {', '.join(missing)}")

        group_columns = [
            "ne_id",
            "cell_id",
            "kpi_name",
            "temporal_profile",
            "day_type",
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
