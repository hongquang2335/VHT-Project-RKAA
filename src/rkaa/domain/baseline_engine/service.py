"""Tính baseline tách biệt theo temporal profile FR-401."""

from __future__ import annotations

import pandas as pd

_BASELINE_KEYS = ["ne_id", "cell_id", "kpi_name", "temporal_profile"]


class BaselineEngine:
    """Baseline chỉ được tính và ghép trong cùng temporal profile."""

    def compute(self, profiled_df: pd.DataFrame) -> pd.DataFrame:
        required = set(_BASELINE_KEYS + ["value"])
        missing = sorted(required.difference(profiled_df.columns))
        if missing:
            raise ValueError(f"Thiếu cột để tính baseline: {', '.join(missing)}")

        group_columns = list(_BASELINE_KEYS)
        if "unit" in profiled_df.columns:
            group_columns.append("unit")

        grouped = profiled_df.groupby(group_columns, dropna=False, sort=True)["value"]
        baseline = grouped.agg(
            sample_count="count",
            mean="mean",
            median="median",
            std="std",
            p05=lambda values: values.quantile(0.05),
            p95=lambda values: values.quantile(0.95),
        )
        return baseline.reset_index()

    def attach_baseline(
        self,
        profiled_df: pd.DataFrame,
        baseline_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Ghép baseline bằng key có temporal_profile để không so sánh chéo profile."""

        missing_records = sorted(set(_BASELINE_KEYS).difference(profiled_df.columns))
        missing_baseline = sorted(set(_BASELINE_KEYS).difference(baseline_df.columns))
        if missing_records:
            raise ValueError(f"Dữ liệu thiếu baseline key: {', '.join(missing_records)}")
        if missing_baseline:
            raise ValueError(f"Baseline thiếu key: {', '.join(missing_baseline)}")

        stats = ["sample_count", "mean", "median", "std", "p05", "p95"]
        available_stats = [column for column in stats if column in baseline_df.columns]
        selected = baseline_df[_BASELINE_KEYS + available_stats].copy()
        selected = selected.rename(
            columns={column: f"baseline_{column}" for column in available_stats}
        )
        return profiled_df.merge(selected, how="left", on=_BASELINE_KEYS, validate="many_to_one")

    def compare_same_profile_windows(
        self,
        pre_df: pd.DataFrame,
        post_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """So sánh pre/post chỉ khi NE + Cell + KPI + temporal profile giống nhau."""

        required = set(_BASELINE_KEYS + ["value"])
        for name, frame in (("pre", pre_df), ("post", post_df)):
            missing = sorted(required.difference(frame.columns))
            if missing:
                raise ValueError(f"{name} thiếu cột: {', '.join(missing)}")

        pre = (
            pre_df.groupby(_BASELINE_KEYS, dropna=False)["value"]
            .agg(pre_count="count", pre_mean="mean", pre_median="median")
            .reset_index()
        )
        post = (
            post_df.groupby(_BASELINE_KEYS, dropna=False)["value"]
            .agg(post_count="count", post_mean="mean", post_median="median")
            .reset_index()
        )
        result = pre.merge(post, how="inner", on=_BASELINE_KEYS, validate="one_to_one")
        result["delta_mean"] = result["post_mean"] - result["pre_mean"]
        denominator = result["pre_mean"].where(result["pre_mean"] != 0)
        result["delta_percent"] = result["delta_mean"] / denominator * 100.0
        return result
