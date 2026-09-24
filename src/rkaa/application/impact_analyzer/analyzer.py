"""FR-301/FR-302 orchestrator built on the existing temporal/baseline cores."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd

from rkaa.application.impact_analyzer.models import ImpactAnalysisConfig
from rkaa.domain.anomaly_detector import AnomalyDetector, ThresholdRule
from rkaa.domain.baseline_engine import BaselineEngine
from rkaa.domain.impact_manager.models import ImpactEvent
from rkaa.domain.statistical_engine import StatisticalEngine
from rkaa.domain.temporal_analyzer.service import TemporalAnalyzer
from rkaa.domain.temporal_analyzer.weekly_cycle import WeeklyCycleAnalyzer

_GROUP_KEYS = ["ne_id", "cell_id", "kpi_name", "temporal_profile", "day_type"]
_REQUIRED_INPUT = {"timestamp", "period_end", "ne_id", "cell_id", "kpi_name", "value"}


class ImpactAnalyzer:
    """Analyze one Impact Event without duplicating temporal or baseline logic.

    Reused core responsibilities:
    - :class:`TemporalAnalyzer`: FR-401 temporal profile classification.
    - :class:`WeeklyCycleAnalyzer`: FR-402 weekday/weekend/day-of-week labels.
    - :class:`BaselineEngine`: same-profile/day-type pre/post matching, historical
      baseline selection, descriptive baseline statistics and BR-01 reliability.

    This class only orchestrates those cores, adds FR-301 statistical tests and
    delegates the final FR-302 decision to :class:`AnomalyDetector`.
    """

    def __init__(
        self,
        *,
        temporal_analyzer: TemporalAnalyzer,
        weekly_cycle_analyzer: WeeklyCycleAnalyzer | None = None,
        baseline_engine: BaselineEngine | None = None,
        statistical_engine: StatisticalEngine | None = None,
        anomaly_detector: AnomalyDetector | None = None,
        config: ImpactAnalysisConfig = ImpactAnalysisConfig(),
    ) -> None:
        self.temporal_analyzer = temporal_analyzer
        self.weekly_cycle_analyzer = weekly_cycle_analyzer or WeeklyCycleAnalyzer()
        self.baseline_engine = baseline_engine or BaselineEngine()
        self.statistical_engine = statistical_engine or StatisticalEngine()
        self.anomaly_detector = anomaly_detector or AnomalyDetector()
        self.config = config

    @staticmethod
    def _utc(value: Any) -> pd.Timestamp:
        parsed = pd.to_datetime(value, errors="coerce", utc=True)
        if pd.isna(parsed):
            raise ValueError(f"Timestamp impact không hợp lệ: {value!r}")
        return pd.Timestamp(parsed)

    @staticmethod
    def _slice(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        # Half-open windows prevent double counting at impact boundaries while
        # preserving exactly window_hours worth of regular samples.
        return frame[(frame["timestamp"] >= start) & (frame["timestamp"] < end)].copy()

    @staticmethod
    def _infer_cadence(series_df: pd.DataFrame) -> pd.Timedelta | None:
        timestamps = pd.Series(series_df["timestamp"].drop_duplicates()).sort_values()
        if len(timestamps) < 2:
            return None
        diffs = timestamps.diff().dropna()
        diffs = diffs[diffs > pd.Timedelta(0)]
        if diffs.empty:
            return None
        cadence = diffs.median()
        return pd.Timedelta(cadence) if cadence > pd.Timedelta(0) else None

    def _expected_group_samples(
        self,
        *,
        start: pd.Timestamp,
        end: pd.Timestamp,
        cadence: pd.Timedelta | None,
        temporal_profile: str,
        day_type: str,
    ) -> int:
        if cadence is None:
            return 0
        grid = pd.date_range(start, end, freq=cadence, inclusive="left")
        if len(grid) == 0:
            return 0
        local = grid.tz_convert(self.temporal_analyzer.config.timezone)
        count = 0
        for timestamp in local:
            minute = timestamp.hour * 60 + timestamp.minute
            profile = self.temporal_analyzer.classify_period(minute)
            current_day_type = self.weekly_cycle_analyzer.classify_day(timestamp.dayofweek)
            if profile == temporal_profile and current_day_type == day_type:
                count += 1
        return count

    def _completeness(
        self,
        group: pd.DataFrame,
        *,
        series_df: pd.DataFrame,
        start: pd.Timestamp,
        end: pd.Timestamp,
        temporal_profile: str,
        day_type: str,
    ) -> float:
        expected = self._expected_group_samples(
            start=start,
            end=end,
            cadence=self._infer_cadence(series_df),
            temporal_profile=temporal_profile,
            day_type=day_type,
        )
        if expected <= 0:
            return np.nan
        observed = int(group["timestamp"].nunique())
        return float(min(observed / expected, 1.0))

    @staticmethod
    def _assessment(
        *,
        delta_abs: float,
        significant: bool,
        direction_preference: str,
    ) -> tuple[str, str]:
        if not np.isfinite(delta_abs) or not significant or abs(delta_abs) <= 1e-12:
            return "NO_CHANGE", "NO_CHANGE"
        direction = "INCREASE" if delta_abs > 0 else "DECREASE"
        preference = direction_preference.strip().lower()
        if preference == "higher_is_better":
            assessment = "IMPROVED" if delta_abs > 0 else "DEGRADED"
        elif preference == "lower_is_better":
            assessment = "IMPROVED" if delta_abs < 0 else "DEGRADED"
        else:
            assessment = "INFORMATIONAL_CHANGE"
        return direction, assessment

    def analyze(
        self,
        clean_df: pd.DataFrame,
        impact: ImpactEvent,
        *,
        kpi_names: list[str] | tuple[str, ...] | None = None,
        direction_preferences: Mapping[str, str] | None = None,
        threshold_rules: Mapping[str, ThresholdRule] | None = None,
    ) -> pd.DataFrame:
        """Run FR-301 and FR-302 for one closed Impact Event.

        ``clean_df`` is expected to be output from FR-201/FR-203. Historical
        baseline is restricted to data before the pre-window to prevent impact
        leakage. The baseline itself is selected by the existing BaselineEngine
        using the same weekday and minute-of-day as the post window.
        """

        missing = sorted(_REQUIRED_INPUT.difference(clean_df.columns))
        if missing:
            raise ValueError(f"FR-301 thiếu input core: {', '.join(missing)}")
        if impact.t2_utc is None:
            raise ValueError("FR-301 chỉ phân tích Impact Event đã có t2")

        working = clean_df.copy()
        working["timestamp"] = pd.to_datetime(
            working["timestamp"], errors="coerce", utc=True, format="mixed"
        )
        working["value"] = pd.to_numeric(working["value"], errors="coerce")
        working = working.dropna(subset=["timestamp", "value"])
        working = working[working["ne_id"].astype(str) == str(impact.ne_id)].copy()
        if impact.cell_id is not None:
            working = working[working["cell_id"].astype(str) == str(impact.cell_id)].copy()
        if kpi_names is not None:
            allowed = {str(name) for name in kpi_names}
            working = working[working["kpi_name"].astype(str).isin(allowed)].copy()
        if working.empty:
            return pd.DataFrame()

        # Reuse FR-401 and FR-402 cores instead of rebuilding time semantics.
        profiled = self.temporal_analyzer.analyze(working).profiled_df
        profiled = self.weekly_cycle_analyzer.analyze(profiled).profiled_df

        t1 = self._utc(impact.t1_utc)
        t2 = self._utc(impact.t2_utc)
        window = pd.Timedelta(hours=self.config.window_hours)
        pre_start, pre_end = t1 - window, t1
        post_start, post_end = t2, t2 + window

        pre = self._slice(profiled, pre_start, pre_end)
        post = self._slice(profiled, post_start, post_end)
        history = profiled[profiled["timestamp"] < pre_start].copy()
        if pre.empty or post.empty:
            return pd.DataFrame()

        # BR-02 pairing is delegated to the existing BaselineEngine.
        scaffold = self.baseline_engine.compare_same_day_type_windows(pre, post)
        if scaffold.empty:
            return pd.DataFrame()

        direction_preferences = direction_preferences or {}
        threshold_rules = threshold_rules or {}
        rows: list[dict[str, Any]] = []

        for pair in scaffold.itertuples(index=False):
            key = {name: getattr(pair, name) for name in _GROUP_KEYS}
            pre_group = pre.copy()
            post_group = post.copy()
            for name, value in key.items():
                pre_group = pre_group[pre_group[name].astype(str) == str(value)]
                post_group = post_group[post_group[name].astype(str) == str(value)]

            pre_stats = self.statistical_engine.describe(pre_group["value"])
            post_stats = self.statistical_engine.describe(post_group["value"])
            welch_p = self.statistical_engine.welch_t_test(
                pre_group["value"], post_group["value"]
            )
            mw_p = self.statistical_engine.mann_whitney_u_test(
                pre_group["value"], post_group["value"]
            )
            significant = self.statistical_engine.is_significant(
                welch_p, mw_p, alpha=self.config.significance_alpha
            )

            series_mask = (
                (profiled["ne_id"].astype(str) == str(key["ne_id"]))
                & (profiled["cell_id"].astype(str) == str(key["cell_id"]))
                & (profiled["kpi_name"].astype(str) == str(key["kpi_name"]))
            )
            series_df = profiled.loc[series_mask]
            pre_completeness = self._completeness(
                pre_group,
                series_df=series_df,
                start=pre_start,
                end=pre_end,
                temporal_profile=str(key["temporal_profile"]),
                day_type=str(key["day_type"]),
            )
            post_completeness = self._completeness(
                post_group,
                series_df=series_df,
                start=post_start,
                end=post_end,
                temporal_profile=str(key["temporal_profile"]),
                day_type=str(key["day_type"]),
            )
            comparison_eligible = bool(
                np.isfinite(pre_completeness)
                and np.isfinite(post_completeness)
                and pre_completeness >= self.config.minimum_completeness
                and post_completeness >= self.config.minimum_completeness
            )

            # Historical baseline selection and reliability are both delegated
            # to BaselineEngine. No duplicate baseline implementation here.
            matched_history = self.baseline_engine.select_corresponding_history(
                history,
                post_group,
            )
            if matched_history.empty:
                baseline_mean = baseline_median = baseline_std = np.nan
                baseline_p05 = baseline_p95 = np.nan
                baseline_sample_count = 0
                baseline_clean_day_count = 0
                baseline_reliable = False
            else:
                baseline = self.baseline_engine.compute(matched_history)
                baseline = self.baseline_engine.annotate_reliability(
                    history,
                    baseline,
                    minimum_clean_days=self.config.minimum_baseline_days,
                )
                row = baseline.iloc[0]
                baseline_sample_count = int(row["sample_count"])
                baseline_mean = float(row["mean"])
                baseline_median = float(row["median"])
                baseline_std = float(row["std"]) if pd.notna(row["std"]) else np.nan
                baseline_p05 = float(row["p05"])
                baseline_p95 = float(row["p95"])
                baseline_clean_day_count = int(row["clean_day_count"])
                baseline_reliable = bool(row["baseline_reliable"])

            delta_abs = float(post_stats.mean - pre_stats.mean)
            delta_percent = (
                float(delta_abs / pre_stats.mean * 100.0)
                if np.isfinite(pre_stats.mean) and abs(pre_stats.mean) > 1e-12
                else np.nan
            )
            preference = str(direction_preferences.get(str(key["kpi_name"]), "informational"))
            change_direction, change_assessment = self._assessment(
                delta_abs=delta_abs,
                significant=significant,
                direction_preference=preference,
            )
            decision = self.anomaly_detector.detect(
                post_mean=post_stats.mean,
                baseline_mean=baseline_mean,
                baseline_std=baseline_std,
                baseline_reliable=baseline_reliable,
                comparison_eligible=comparison_eligible,
                delta_percent=delta_percent,
                threshold_rule=threshold_rules.get(str(key["kpi_name"])),
            )

            rows.append(
                {
                    **key,
                    "impact_id": impact.impact_id,
                    "impact_type": impact.impact_type,
                    "impact_description": impact.description,
                    "impact_operator": impact.operator,
                    "pre_start": pre_start,
                    "pre_end": pre_end,
                    "post_start": post_start,
                    "post_end": post_end,
                    "pre_count": pre_stats.count,
                    "pre_mean": pre_stats.mean,
                    "pre_median": pre_stats.median,
                    "pre_std": pre_stats.std,
                    "pre_p05": pre_stats.p05,
                    "pre_p95": pre_stats.p95,
                    "post_count": post_stats.count,
                    "post_mean": post_stats.mean,
                    "post_median": post_stats.median,
                    "post_std": post_stats.std,
                    "post_p05": post_stats.p05,
                    "post_p95": post_stats.p95,
                    "delta_abs": delta_abs,
                    "delta_percent": delta_percent,
                    "welch_t_p_value": welch_p,
                    "mann_whitney_p_value": mw_p,
                    "statistically_significant": significant,
                    "direction_preference": preference,
                    "change_direction": change_direction,
                    "change_assessment": change_assessment,
                    "pre_completeness": pre_completeness,
                    "post_completeness": post_completeness,
                    "comparison_eligible": comparison_eligible,
                    "baseline_reference": "SAME_WEEKDAY_SAME_MINUTE_OF_DAY",
                    "baseline_sample_count": baseline_sample_count,
                    "baseline_mean": baseline_mean,
                    "baseline_median": baseline_median,
                    "baseline_std": baseline_std,
                    "baseline_p05": baseline_p05,
                    "baseline_p95": baseline_p95,
                    "baseline_clean_day_count": baseline_clean_day_count,
                    "baseline_reliable": baseline_reliable,
                    "sigma_applicable": decision.sigma_applicable,
                    "reference_z_score": decision.reference_z_score,
                    "anomaly_3sigma": decision.anomaly_3sigma,
                    "threshold_configured": decision.threshold_configured,
                    "threshold_severity": decision.threshold_severity,
                    "anomaly_threshold": decision.anomaly_threshold,
                    "anomaly_flag": decision.anomaly_flag,
                    "anomaly_source": decision.anomaly_source,
                    "anomaly_decision_source": decision.anomaly_decision_source,
                }
            )

        return pd.DataFrame(rows).sort_values(_GROUP_KEYS).reset_index(drop=True)
