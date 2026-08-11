"""Điều phối các bước lọc của FR-201 theo đúng thứ tự SRS."""

from __future__ import annotations

import pandas as pd

from rkaa.domain.noise_filter.custom_rule_filter import CustomRuleFilter
from rkaa.domain.noise_filter.impact_window_filter import ImpactWindowFilter
from rkaa.domain.noise_filter.models import CleanResult, ExclusionWindow, NoiseFilterConfig
from rkaa.domain.noise_filter.null_sentinel_filter import NullSentinelFilter
from rkaa.domain.noise_filter.restart_filter import RestartFilter
from rkaa.domain.noise_filter.statistical_outlier_filter import StatisticalOutlierFilter
from rkaa.domain.noise_filter.utils import empty_excluded_like, require_columns


class NoiseFilterService:
    """Chạy Null → Impact → Restart → Statistical → Custom Rule."""

    def __init__(
        self,
        config: NoiseFilterConfig,
        *,
        exclusion_windows: list[ExclusionWindow] | None = None,
    ) -> None:
        self.config = config
        self.exclusion_windows = list(exclusion_windows or [])

    def filter(self, df: pd.DataFrame) -> CleanResult:
        require_columns(
            df,
            ("timestamp", "period_end", "ne_id", "cell_id", "kpi_name", "value"),
        )

        current = df.copy()
        excluded_parts: list[pd.DataFrame] = []
        filter_summary: dict[str, object] = {}

        steps = [
            (
                "null_sentinel",
                self.config.null_sentinel.enabled,
                NullSentinelFilter(self.config.null_sentinel),
            ),
            (
                "impact_window",
                self.config.impact_window.enabled,
                ImpactWindowFilter(self.config.impact_window, self.exclusion_windows),
            ),
            (
                "restart",
                self.config.restart.enabled,
                RestartFilter(self.config.restart),
            ),
            (
                "statistical_outlier",
                self.config.statistical_outlier.enabled,
                StatisticalOutlierFilter(self.config.statistical_outlier),
            ),
            (
                "custom_rule",
                self.config.custom_rule.enabled,
                CustomRuleFilter(self.config.custom_rule),
            ),
        ]

        for name, enabled, rule in steps:
            if not enabled:
                filter_summary[name] = {"status": "DISABLED", "excluded": 0}
                continue

            outcome = rule.apply(current)
            current = outcome.cleaned_df
            if not outcome.excluded_df.empty:
                excluded_parts.append(outcome.excluded_df)
            filter_summary[name] = outcome.summary

        if excluded_parts:
            excluded = pd.concat(excluded_parts, ignore_index=True)
        else:
            excluded = empty_excluded_like(df)

        return CleanResult(
            cleaned_df=current.reset_index(drop=True),
            excluded_df=excluded.reset_index(drop=True),
            summary={
                "input_records": len(df),
                "cleaned_records": len(current),
                "excluded_records": len(excluded),
                "filters": filter_summary,
            },
        )
