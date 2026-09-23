"""Periodic comparison engine used by FR-401/402.

This module ports the useful parts of FR-301/302 (descriptive before/after
statistics, significance tests, 3-sigma and configurable thresholds) to
calendar/temporal cycles instead of Impact Events.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.stats import norm, ttest_ind_from_stats

from rkaa.domain.threshold_manager import ThresholdManager

_BASE_KEYS = ["ne_id", "cell_id", "kpi_name"]


@dataclass(frozen=True, slots=True)
class StatisticalComparisonConfig:
    alpha: float = 0.05
    sigma_threshold: float = 3.0
    minimum_samples_per_group: int = 3

    def __post_init__(self) -> None:
        if not 0 < self.alpha < 1:
            raise ValueError("alpha phải nằm trong (0, 1)")
        if self.sigma_threshold <= 0:
            raise ValueError("sigma_threshold phải > 0")
        if self.minimum_samples_per_group < 2:
            raise ValueError("minimum_samples_per_group phải >= 2")


@dataclass(frozen=True, slots=True)
class DailyCycleComparisonConfig:
    current_window_hours: int = 24
    comparison_lags_hours: tuple[int, ...] = (72, 144, 288)

    def __post_init__(self) -> None:
        if self.current_window_hours <= 0:
            raise ValueError("current_window_hours phải > 0")
        if not self.comparison_lags_hours:
            raise ValueError("comparison_lags_hours không được rỗng")
        if any(value <= 0 for value in self.comparison_lags_hours):
            raise ValueError("mọi comparison lag phải > 0")


@dataclass(frozen=True, slots=True)
class WeeklyCycleComparisonConfig:
    current_window_days: int = 7
    previous_week_enabled: bool = True
    previous_month_enabled: bool = False
    previous_month_window_days: int = 30

    def __post_init__(self) -> None:
        if self.current_window_days <= 0:
            raise ValueError("current_window_days phải > 0")
        if self.previous_month_window_days <= 0:
            raise ValueError("previous_month_window_days phải > 0")


class CycleComparisonAnalyzer:
    """So sánh rolling cycles trên từng NE + Cell + KPI."""

    def __init__(
        self,
        statistical_config: StatisticalComparisonConfig,
        *,
        threshold_manager: ThresholdManager | None = None,
    ) -> None:
        self.statistical_config = statistical_config
        self.threshold_manager = threshold_manager or ThresholdManager([])

    @staticmethod
    def _prepare(df: pd.DataFrame, required_extra: Iterable[str] = ()) -> pd.DataFrame:
        required = set(_BASE_KEYS + ["timestamp", "value", *required_extra])
        missing = sorted(required.difference(df.columns))
        if missing:
            raise ValueError(f"Thiếu cột để so sánh chu kỳ: {', '.join(missing)}")

        working = df.copy()
        working["timestamp"] = pd.to_datetime(
            working["timestamp"], errors="coerce", utc=True, format="mixed"
        )
        working["value"] = pd.to_numeric(working["value"], errors="coerce")
        working = working.dropna(subset=["timestamp", "value"])
        return working

    @staticmethod
    def _window(df: pd.DataFrame, *, end: pd.Timestamp, duration: pd.Timedelta) -> pd.DataFrame:
        # Open-left, closed-right gives exactly 24 hourly samples for a regular
        # hourly series when end is the latest timestamp.
        start = end - duration
        return df[(df["timestamp"] > start) & (df["timestamp"] <= end)].copy()

    @staticmethod
    def _range(df: pd.DataFrame, *, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        """Open-left, closed-right helper for historical ranges."""

        return df[(df["timestamp"] > start) & (df["timestamp"] <= end)].copy()

    @staticmethod
    def _average_daily_cycle(
        df: pd.DataFrame,
        *,
        group_columns: list[str],
    ) -> pd.DataFrame:
        """Collapse a historical range into one mean daily cycle.

        The returned frame keeps one averaged value per minute-of-day for every
        logical group. This allows FR-401 to compare the latest clean 24-hour
        cycle against historical *mean* daily cycles instead of three single
        reference days.
        """

        if df.empty:
            return df.copy()

        working = df.copy()
        if "minute_of_day" not in working.columns:
            local = pd.to_datetime(working["timestamp"], utc=True, format="mixed")
            working["minute_of_day"] = local.dt.hour * 60 + local.dt.minute
        if "time_of_day" not in working.columns:
            working["time_of_day"] = (
                pd.to_timedelta(working["minute_of_day"], unit="m")
                .astype(str)
                .str.slice(0, 5)
            )

        cycle_columns = [*group_columns, "minute_of_day", "time_of_day"]
        aggregated = (
            working.groupby(cycle_columns, dropna=False, sort=True)
            .agg(
                value=("value", "mean"),
                timestamp=("timestamp", "max"),
            )
            .reset_index()
        )
        if "unit" in working.columns:
            units = (
                working.groupby(cycle_columns, dropna=False, sort=True)["unit"]
                .first()
                .reset_index()
            )
            aggregated = aggregated.merge(
                units,
                how="left",
                on=cycle_columns,
                validate="one_to_one",
            )
        return aggregated

    def compare_daily_cycles(
        self,
        profiled_df: pd.DataFrame,
        config: DailyCycleComparisonConfig,
    ) -> pd.DataFrame:
        """FR-401: latest 24h vs historical mean daily cycles.

        The current cycle is the latest clean 24-hour window. Each reference is
        a *mean daily cycle* computed from all clean data in the cumulative
        historical range ``(T-endpoint, T-24h]`` where ``endpoint`` is one of
        ``comparison_lags_hours`` such as 72h, 144h, or 288h.
        """

        working = self._prepare(profiled_df, ["temporal_profile"])
        if working.empty:
            return pd.DataFrame()
        anchor_end = working["timestamp"].max()
        current_duration = pd.Timedelta(hours=config.current_window_hours)
        current_start = anchor_end - current_duration
        current = self._window(working, end=anchor_end, duration=current_duration)

        rows: list[dict[str, object]] = []
        for lag_hours in config.comparison_lags_hours:
            reference_start = anchor_end - pd.Timedelta(hours=lag_hours)
            reference_end = current_start
            reference_source = self._range(
                working,
                start=reference_start,
                end=reference_end,
            )
            reference = self._average_daily_cycle(
                reference_source,
                group_columns=[*_BASE_KEYS, "temporal_profile"],
            )
            rows.extend(
                self._compare_grouped(
                    current,
                    reference,
                    group_columns=[*_BASE_KEYS, "temporal_profile"],
                    comparison_kind="FR401_DAILY_CYCLE",
                    reference_label=f"24H_TO_{lag_hours}H_AVG",
                    current_start=current_start,
                    current_end=anchor_end,
                    reference_start=reference_start,
                    reference_end=reference_end,
                )
            )
        return pd.DataFrame(rows)

    def compare_weekly_cycles(
        self,
        profiled_df: pd.DataFrame,
        config: WeeklyCycleComparisonConfig,
    ) -> pd.DataFrame:
        """FR-402: latest week vs previous week, optionally latest month vs previous month.

        Both day-type and individual weekday views are emitted in one table using
        ``group_scope``/``group_value``.
        """

        working = self._prepare(
            profiled_df,
            ["temporal_profile", "day_type", "day_of_week"],
        )
        if working.empty:
            return pd.DataFrame()
        anchor_end = working["timestamp"].max()
        rows: list[dict[str, object]] = []

        if config.previous_week_enabled:
            duration = pd.Timedelta(days=config.current_window_days)
            current = self._window(working, end=anchor_end, duration=duration)
            reference_end = anchor_end - duration
            reference = self._window(working, end=reference_end, duration=duration)
            rows.extend(
                self._weekly_group_rows(
                    current,
                    reference,
                    comparison_kind="FR402_WEEK_OVER_WEEK",
                    reference_label="PREVIOUS_WEEK",
                    current_start=anchor_end - duration,
                    current_end=anchor_end,
                    reference_start=reference_end - duration,
                    reference_end=reference_end,
                )
            )

        if config.previous_month_enabled:
            duration = pd.Timedelta(days=config.previous_month_window_days)
            current = self._window(working, end=anchor_end, duration=duration)
            reference_end = anchor_end - duration
            reference = self._window(working, end=reference_end, duration=duration)
            rows.extend(
                self._weekly_group_rows(
                    current,
                    reference,
                    comparison_kind="FR402_MONTH_OVER_MONTH",
                    reference_label="PREVIOUS_MONTH",
                    current_start=anchor_end - duration,
                    current_end=anchor_end,
                    reference_start=reference_end - duration,
                    reference_end=reference_end,
                )
            )
        return pd.DataFrame(rows)

    def _weekly_group_rows(
        self,
        current: pd.DataFrame,
        reference: pd.DataFrame,
        **metadata: object,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for scope, dimension in (("DAY_TYPE", "day_type"), ("DAY_OF_WEEK", "day_of_week")):
            compared = self._compare_grouped(
                current,
                reference,
                group_columns=[*_BASE_KEYS, "temporal_profile", dimension],
                **metadata,
            )
            for row in compared:
                row["group_scope"] = scope
                row["group_value"] = row.pop(dimension)
            rows.extend(compared)
        return rows

    def _compare_grouped(
        self,
        current: pd.DataFrame,
        reference: pd.DataFrame,
        *,
        group_columns: list[str],
        comparison_kind: str,
        reference_label: str,
        current_start: pd.Timestamp,
        current_end: pd.Timestamp,
        reference_start: pd.Timestamp,
        reference_end: pd.Timestamp,
    ) -> list[dict[str, object]]:
        if current.empty or reference.empty:
            return []

        current_stats = self._descriptive_stats(current, group_columns, "current")
        reference_stats = self._descriptive_stats(reference, group_columns, "reference")
        result = current_stats.merge(
            reference_stats,
            how="inner",
            on=group_columns,
            validate="one_to_one",
        )
        if result.empty:
            return []

        min_samples = self.statistical_config.minimum_samples_per_group
        result["comparison_eligible"] = (
            (result["current_count"] >= min_samples)
            & (result["reference_count"] >= min_samples)
        )
        result["delta_abs"] = result["current_mean"] - result["reference_mean"]
        denominator = result["reference_mean"].where(
            result["reference_mean"].abs() > 1e-12
        )
        result["delta_percent"] = result["delta_abs"] / denominator * 100.0

        reference_std = pd.to_numeric(result["reference_std"], errors="coerce")
        result["sigma_applicable"] = (
            result["comparison_eligible"]
            & reference_std.notna()
            & np.isfinite(reference_std)
            & (reference_std.abs() > 1e-12)
        )
        result["reference_z_score"] = np.nan
        sigma_mask = result["sigma_applicable"]
        result.loc[sigma_mask, "reference_z_score"] = (
            result.loc[sigma_mask, "delta_abs"] / reference_std.loc[sigma_mask]
        )
        result["anomaly_3sigma"] = (
            result["sigma_applicable"]
            & (result["reference_z_score"].abs() >= self.statistical_config.sigma_threshold)
        )

        result["welch_t_p_value"] = self._welch_p_values(result)
        mw = self._mann_whitney_p_values(current, reference, group_columns)
        result = result.merge(mw, how="left", on=group_columns, validate="one_to_one")
        result.loc[~result["comparison_eligible"], "mann_whitney_p_value"] = np.nan

        min_p = result[["welch_t_p_value", "mann_whitney_p_value"]].min(
            axis=1, skipna=True
        )
        result["statistically_significant"] = (
            result["comparison_eligible"]
            & min_p.notna()
            & (min_p < self.statistical_config.alpha)
        )

        threshold_rows = []
        for row in result[["kpi_name", "delta_abs", "delta_percent"]].itertuples(
            index=False
        ):
            delta_percent = float(row.delta_percent)
            threshold_rows.append(
                self.threshold_manager.evaluate(
                    str(row.kpi_name),
                    delta_abs=float(row.delta_abs),
                    delta_percent=(
                        delta_percent if math.isfinite(delta_percent) else None
                    ),
                )
            )
        threshold_df = pd.DataFrame(threshold_rows, index=result.index)
        for column in threshold_df.columns:
            result[column] = threshold_df[column]
        result["anomaly_threshold"] = result["threshold_severity"].isin(
            ["WARNING", "CRITICAL"]
        )

        # FR-303 is the operational authority whenever an operator-configured
        # threshold exists for the actual direction of change.  FR-302 3-sigma
        # remains visible as diagnostic evidence, but is only the decision
        # fallback when FR-303 has no applicable threshold.
        threshold_authority = result["threshold_configured"].fillna(False).astype(bool)
        result["anomaly_decision_source"] = np.where(
            threshold_authority,
            "FR303_THRESHOLD",
            "FR302_3SIGMA",
        )
        result["anomaly_flag"] = np.where(
            threshold_authority,
            result["anomaly_threshold"],
            result["anomaly_3sigma"],
        ).astype(bool)
        result["anomaly_source"] = np.where(
            result["anomaly_flag"],
            result["anomaly_decision_source"],
            "NONE",
        )

        result["comparison_kind"] = comparison_kind
        result["reference_label"] = reference_label
        result["current_start"] = current_start
        result["current_end"] = current_end
        result["reference_start"] = reference_start
        result["reference_end"] = reference_end

        if "unit" in current.columns:
            units = (
                current.groupby(group_columns, dropna=False, sort=False)["unit"]
                .first()
                .reset_index()
            )
            result = result.merge(units, how="left", on=group_columns, validate="one_to_one")
        return result.to_dict(orient="records")

    @staticmethod
    def _descriptive_stats(
        frame: pd.DataFrame,
        group_columns: list[str],
        prefix: str,
    ) -> pd.DataFrame:
        grouped = frame.groupby(group_columns, dropna=False, sort=False)["value"]
        basic = grouped.agg(
            count="count",
            mean="mean",
            median="median",
            std="std",
        ).reset_index()
        quantiles = (
            grouped.quantile([0.05, 0.95])
            .unstack(level=-1)
            .rename(columns={0.05: "p05", 0.95: "p95"})
            .reset_index()
        )
        stats = basic.merge(
            quantiles,
            how="left",
            on=group_columns,
            validate="one_to_one",
        )
        return stats.rename(
            columns={
                name: f"{prefix}_{name}"
                for name in ("count", "mean", "median", "std", "p05", "p95")
            }
        )

    @staticmethod
    def _welch_p_values(result: pd.DataFrame) -> np.ndarray:
        eligible = result["comparison_eligible"].to_numpy(dtype=bool)
        current_std = result["current_std"].fillna(0.0).to_numpy(dtype=float)
        reference_std = result["reference_std"].fillna(0.0).to_numpy(dtype=float)
        current_mean = result["current_mean"].to_numpy(dtype=float)
        reference_mean = result["reference_mean"].to_numpy(dtype=float)
        p_values = np.full(len(result), np.nan, dtype=float)

        both_constant = eligible & (np.abs(current_std) <= 1e-12) & (
            np.abs(reference_std) <= 1e-12
        )
        p_values[both_constant] = np.where(
            np.abs(current_mean[both_constant] - reference_mean[both_constant]) <= 1e-12,
            1.0,
            0.0,
        )
        variable = eligible & ~both_constant
        if variable.any():
            test = ttest_ind_from_stats(
                mean1=current_mean[variable],
                std1=current_std[variable],
                nobs1=result.loc[variable, "current_count"].to_numpy(dtype=float),
                mean2=reference_mean[variable],
                std2=reference_std[variable],
                nobs2=result.loc[variable, "reference_count"].to_numpy(dtype=float),
                equal_var=False,
            )
            p_values[variable] = np.asarray(test.pvalue, dtype=float)
        return p_values

    @staticmethod
    def _mann_whitney_p_values(
        current: pd.DataFrame,
        reference: pd.DataFrame,
        group_columns: list[str],
    ) -> pd.DataFrame:
        """Vectorized asymptotic Mann-Whitney U with tie correction.

        Calling scipy ``mannwhitneyu`` once per KPI/profile is prohibitively slow
        on production-sized data. This computes the same rank-sum statistic in
        bulk using pandas groupby/rank, then uses the normal approximation.
        """

        current_part = current[group_columns + ["value"]].copy()
        current_part["_is_current"] = True
        reference_part = reference[group_columns + ["value"]].copy()
        reference_part["_is_current"] = False
        combined = pd.concat([current_part, reference_part], ignore_index=True)
        if combined.empty:
            return pd.DataFrame(columns=[*group_columns, "mann_whitney_p_value"])

        groupers = [combined[column] for column in group_columns]
        combined["_rank"] = combined.groupby(
            groupers, dropna=False, sort=False
        )["value"].rank(method="average")

        total = (
            combined.groupby(group_columns, dropna=False, sort=False)
            .size()
            .rename("_n_total")
            .reset_index()
        )
        current_rank = (
            combined.loc[combined["_is_current"]]
            .groupby(group_columns, dropna=False, sort=False)
            .agg(_n_current=("value", "size"), _rank_sum_current=("_rank", "sum"))
            .reset_index()
        )
        reference_count = (
            combined.loc[~combined["_is_current"]]
            .groupby(group_columns, dropna=False, sort=False)
            .size()
            .rename("_n_reference")
            .reset_index()
        )
        tie_counts = (
            combined.groupby(group_columns + ["value"], dropna=False, sort=False)
            .size()
            .rename("_tie_count")
            .reset_index()
        )
        tie_counts["_tie_term"] = tie_counts["_tie_count"] ** 3 - tie_counts["_tie_count"]
        tie_term = (
            tie_counts.groupby(group_columns, dropna=False, sort=False)["_tie_term"]
            .sum()
            .reset_index()
        )
        stats = total.merge(current_rank, on=group_columns, how="inner").merge(
            reference_count, on=group_columns, how="inner"
        ).merge(tie_term, on=group_columns, how="left")

        n1 = stats["_n_current"].to_numpy(dtype=float)
        n2 = stats["_n_reference"].to_numpy(dtype=float)
        n = stats["_n_total"].to_numpy(dtype=float)
        rank_sum = stats["_rank_sum_current"].to_numpy(dtype=float)
        tie = stats["_tie_term"].fillna(0.0).to_numpy(dtype=float)
        u1 = rank_sum - n1 * (n1 + 1.0) / 2.0
        mean_u = n1 * n2 / 2.0
        tie_adjustment = np.zeros_like(n)
        valid_n = n > 1
        tie_adjustment[valid_n] = tie[valid_n] / (n[valid_n] * (n[valid_n] - 1.0))
        variance = n1 * n2 / 12.0 * (n + 1.0 - tie_adjustment)
        p_values = np.ones_like(variance)
        valid_variance = variance > 1e-12
        continuity = 0.5 * np.sign(u1 - mean_u)
        z = np.zeros_like(variance)
        z[valid_variance] = (
            u1[valid_variance] - mean_u[valid_variance] - continuity[valid_variance]
        ) / np.sqrt(variance[valid_variance])
        p_values[valid_variance] = 2.0 * norm.sf(np.abs(z[valid_variance]))
        stats["mann_whitney_p_value"] = p_values
        return stats[group_columns + ["mann_whitney_p_value"]]
