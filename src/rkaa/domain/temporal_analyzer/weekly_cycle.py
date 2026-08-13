"""FR-402 weekday/weekend classification and profile aggregation."""

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
    """Classify KPI records as WEEKDAY/WEEKEND using the FR-401 profile timezone."""

    @staticmethod
    def classify_day(weekday_index: int) -> str:
        if not 0 <= weekday_index <= 6:
            raise ValueError(f"weekday_index must be in [0, 6], got {weekday_index}")
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
                "FR-402 expects one profile_timezone in the input; "
                f"got {sorted(unique)}"
            )
        try:
            ZoneInfo(unique[0])
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Invalid profile_timezone: {unique[0]}") from exc
        return unique[0]

    def analyze(self, df: pd.DataFrame) -> WeeklyCycleAnalysisResult:
        missing = sorted(_REQUIRED_COLUMNS.difference(df.columns))
        if missing:
            raise ValueError(f"Missing required FR-402 columns: {', '.join(missing)}")

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
                f"FR-402 received {bad} invalid timestamp values; run FR-203 first"
            )

        values = pd.to_numeric(working["value"], errors="coerce")
        if values.isna().any():
            bad = int(values.isna().sum())
            raise ValueError(
                f"FR-402 received {bad} non-numeric values; run FR-203/FR-201 first"
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
        """Aggregate the same time-of-day separately for WEEKDAY and WEEKEND."""

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
            raise ValueError(f"Missing FR-402 overlay columns: {', '.join(missing)}")

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
