"""Điều phối phân tích KPI trước/sau Impact Event cho FR-301."""

from __future__ import annotations

import math
from datetime import timedelta

import pandas as pd

from rkaa.domain.baseline_engine import BaselineEngine
from rkaa.domain.impact_analyzer.models import ImpactAnalysisResult, ImpactTrendAssessment
from rkaa.domain.impact_manager.models import ImpactEvent
from rkaa.domain.statistical_engine import ChangeDirection, StatisticalEngine

_PROFILE_KEYS = ["ne_id", "cell_id", "kpi_name", "temporal_profile"]
_DAY_TYPE_KEYS = _PROFILE_KEYS + ["day_type"]


def _assess_trend(
    *,
    kpi_name: str,
    change_direction: str,
    statistically_significant: bool,
    direction_preferences: dict[str, str],
    has_statistical_test: bool,
) -> str:
    if not has_statistical_test:
        return ImpactTrendAssessment.INSUFFICIENT_DATA.value
    if not statistically_significant or change_direction == ChangeDirection.UNCHANGED.value:
        return ImpactTrendAssessment.UNCHANGED.value

    preference = direction_preferences.get(kpi_name, "informational")
    if preference == "higher_is_better":
        return (
            ImpactTrendAssessment.IMPROVED.value
            if change_direction == ChangeDirection.INCREASE.value
            else ImpactTrendAssessment.DEGRADED.value
        )
    if preference == "lower_is_better":
        return (
            ImpactTrendAssessment.DEGRADED.value
            if change_direction == ChangeDirection.INCREASE.value
            else ImpactTrendAssessment.IMPROVED.value
        )
    return ImpactTrendAssessment.INFORMATIONAL.value


class ImpactAnalyzerService:
    """Tạo cửa sổ trước/sau, giữ cùng ngữ cảnh và tính thống kê FR-301."""

    def __init__(
        self,
        *,
        baseline_engine: BaselineEngine | None = None,
        statistical_engine: StatisticalEngine | None = None,
    ) -> None:
        self.baseline_engine = baseline_engine or BaselineEngine()
        self.statistical_engine = statistical_engine or StatisticalEngine()

    def analyze(
        self,
        profiled_df: pd.DataFrame,
        event: ImpactEvent,
        *,
        window_hours: float = 24.0,
        kpi_names: list[str] | None = None,
        direction_preferences: dict[str, str] | None = None,
    ) -> ImpactAnalysisResult:
        """Phân tích các KPI trong cửa sổ trước và sau một sự kiện đã kết thúc."""

        if event.t2_utc is None:
            raise ValueError("FR-301 cần Impact Event đã có t2 để xác định post-window")
        if window_hours <= 0:
            raise ValueError("window_hours phải > 0")

        required = set(_PROFILE_KEYS + ["timestamp", "value"])
        missing = sorted(required.difference(profiled_df.columns))
        if missing:
            raise ValueError(f"Thiếu cột bắt buộc cho FR-301: {', '.join(missing)}")

        working = profiled_df.copy()
        timestamps = pd.to_datetime(
            working["timestamp"],
            errors="coerce",
            utc=True,
            format="mixed",
        )
        if timestamps.isna().any():
            raise ValueError("FR-301 nhận timestamp không hợp lệ")
        working["timestamp"] = timestamps
        working["value"] = pd.to_numeric(working["value"], errors="coerce")
        working = working[working["value"].notna()].copy()

        working = working[working["ne_id"].astype(str) == event.ne_id]
        if event.cell_id is not None:
            working = working[working["cell_id"].astype(str) == event.cell_id]
        if kpi_names:
            selected_kpis = {str(item).strip() for item in kpi_names if str(item).strip()}
            working = working[working["kpi_name"].astype(str).isin(selected_kpis)]

        window = timedelta(hours=float(window_hours))
        pre_start = event.t1_utc - window
        post_end = event.t2_utc + window

        # Dùng [đầu, cuối) để không đưa mốc bắt đầu tác động vào cửa sổ trước.
        pre_df = working[
            (working["timestamp"] >= pre_start) & (working["timestamp"] < event.t1_utc)
        ].copy()
        post_df = working[
            (working["timestamp"] >= event.t2_utc) & (working["timestamp"] < post_end)
        ].copy()

        use_day_type = "day_type" in working.columns
        group_keys = _DAY_TYPE_KEYS if use_day_type else _PROFILE_KEYS
        if use_day_type:
            paired = self.baseline_engine.compare_same_day_type_windows(pre_df, post_df)
        else:
            paired = self.baseline_engine.compare_same_profile_windows(pre_df, post_df)

        if paired.empty:
            report = self.statistical_engine.compare_groups(
                pre_df.iloc[0:0],
                post_df.iloc[0:0],
                group_keys=group_keys,
            )
        else:
            paired_keys = paired[group_keys].drop_duplicates()
            pre_paired = pre_df.merge(paired_keys, how="inner", on=group_keys)
            post_paired = post_df.merge(paired_keys, how="inner", on=group_keys)
            report = self.statistical_engine.compare_groups(
                pre_paired,
                post_paired,
                group_keys=group_keys,
            )

        preferences = direction_preferences or {}
        if not report.empty:
            has_test = report[["t_test_p_value", "mann_whitney_p_value"]].apply(
                lambda row: any(math.isfinite(float(value)) for value in row if pd.notna(value)),
                axis=1,
            )
            report["trend_assessment"] = [
                _assess_trend(
                    kpi_name=str(row.kpi_name),
                    change_direction=str(row.change_direction),
                    statistically_significant=bool(row.statistically_significant),
                    direction_preferences=preferences,
                    has_statistical_test=bool(test_available),
                )
                for row, test_available in zip(
                    report.itertuples(index=False),
                    has_test.tolist(),
                    strict=True,
                )
            ]

        metadata = {
            "impact_id": event.impact_id,
            "impact_type": event.impact_type,
            "event_category": event.event_category.value,
            "impact_t1_utc": event.t1_utc.isoformat(),
            "impact_t2_utc": event.t2_utc.isoformat(),
            "pre_window_start_utc": pre_start.isoformat(),
            "pre_window_end_utc": event.t1_utc.isoformat(),
            "post_window_start_utc": event.t2_utc.isoformat(),
            "post_window_end_utc": post_end.isoformat(),
            "window_hours": float(window_hours),
        }
        for column, value in reversed(list(metadata.items())):
            report.insert(0, column, value)

        return ImpactAnalysisResult(
            pre_df=pre_df.reset_index(drop=True),
            post_df=post_df.reset_index(drop=True),
            report_df=report.reset_index(drop=True),
        )
