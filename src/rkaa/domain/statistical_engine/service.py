"""Tính thống kê mô tả và kiểm định trước/sau cho FR-301."""

from __future__ import annotations

import math

import pandas as pd
from scipy import stats

from rkaa.domain.statistical_engine.models import ChangeDirection, StatisticalTestConfig


_DESCRIPTIVE_COLUMNS = ["count", "mean", "median", "std", "p05", "p95"]


def _describe(values: pd.Series) -> dict[str, float | int]:
    numeric = pd.to_numeric(values, errors="coerce").dropna().astype(float)
    return {
        "count": int(numeric.count()),
        "mean": float(numeric.mean()) if not numeric.empty else math.nan,
        "median": float(numeric.median()) if not numeric.empty else math.nan,
        "std": float(numeric.std(ddof=1)) if len(numeric) >= 2 else math.nan,
        "p05": float(numeric.quantile(0.05)) if not numeric.empty else math.nan,
        "p95": float(numeric.quantile(0.95)) if not numeric.empty else math.nan,
    }


def _welch_t_test(pre_values: pd.Series, post_values: pd.Series) -> float:
    pre = pd.to_numeric(pre_values, errors="coerce").dropna().astype(float)
    post = pd.to_numeric(post_values, errors="coerce").dropna().astype(float)
    if len(pre) < 2 or len(post) < 2:
        return math.nan
    result = stats.ttest_ind(pre, post, equal_var=False, nan_policy="omit")
    return float(result.pvalue) if math.isfinite(float(result.pvalue)) else math.nan


def _mann_whitney_test(pre_values: pd.Series, post_values: pd.Series) -> float:
    pre = pd.to_numeric(pre_values, errors="coerce").dropna().astype(float)
    post = pd.to_numeric(post_values, errors="coerce").dropna().astype(float)
    if pre.empty or post.empty:
        return math.nan
    try:
        result = stats.mannwhitneyu(pre, post, alternative="two-sided", method="auto")
    except ValueError:
        return math.nan
    return float(result.pvalue) if math.isfinite(float(result.pvalue)) else math.nan


def _change_direction(delta: float) -> ChangeDirection:
    if not math.isfinite(delta) or math.isclose(delta, 0.0, abs_tol=1e-12):
        return ChangeDirection.UNCHANGED
    return ChangeDirection.INCREASE if delta > 0 else ChangeDirection.DECREASE


class StatisticalEngine:
    """So sánh thống kê hai tập dữ liệu trong cùng ngữ cảnh nghiệp vụ."""

    def __init__(self, config: StatisticalTestConfig | None = None) -> None:
        self.config = config or StatisticalTestConfig()

    def compare_groups(
        self,
        pre_df: pd.DataFrame,
        post_df: pd.DataFrame,
        *,
        group_keys: list[str],
    ) -> pd.DataFrame:
        """Tính thống kê và kiểm định cho các nhóm xuất hiện ở cả cửa sổ trước và sau."""

        required = set(group_keys + ["value"])
        for name, frame in (("pre", pre_df), ("post", post_df)):
            missing = sorted(required.difference(frame.columns))
            if missing:
                raise ValueError(f"{name} thiếu cột: {', '.join(missing)}")

        pre_groups = {
            tuple(key if isinstance(key, tuple) else (key,)): frame
            for key, frame in pre_df.groupby(group_keys, dropna=False, sort=True)
        }
        post_groups = {
            tuple(key if isinstance(key, tuple) else (key,)): frame
            for key, frame in post_df.groupby(group_keys, dropna=False, sort=True)
        }

        shared_keys = sorted(set(pre_groups).intersection(post_groups), key=lambda item: str(item))
        rows: list[dict[str, object]] = []
        for key_values in shared_keys:
            pre_group = pre_groups[key_values]
            post_group = post_groups[key_values]
            pre_stats = _describe(pre_group["value"])
            post_stats = _describe(post_group["value"])

            delta_mean = float(post_stats["mean"]) - float(pre_stats["mean"])
            pre_mean = float(pre_stats["mean"])
            delta_percent = (
                delta_mean / pre_mean * 100.0
                if math.isfinite(pre_mean) and not math.isclose(pre_mean, 0.0, abs_tol=1e-12)
                else math.nan
            )
            t_p = _welch_t_test(pre_group["value"], post_group["value"])
            mw_p = _mann_whitney_test(pre_group["value"], post_group["value"])
            valid_p_values = [value for value in (t_p, mw_p) if math.isfinite(value)]
            significant = bool(valid_p_values and min(valid_p_values) < self.config.alpha)

            row: dict[str, object] = dict(zip(group_keys, key_values, strict=True))
            for prefix, values in (("pre", pre_stats), ("post", post_stats)):
                for column in _DESCRIPTIVE_COLUMNS:
                    row[f"{prefix}_{column}"] = values[column]
            row.update(
                {
                    "delta_mean": delta_mean,
                    "delta_percent": delta_percent,
                    "change_direction": _change_direction(delta_mean).value,
                    "t_test_p_value": t_p,
                    "mann_whitney_p_value": mw_p,
                    "statistically_significant": significant,
                    "significance_alpha": self.config.alpha,
                }
            )
            rows.append(row)

        columns = [
            *group_keys,
            *[f"pre_{column}" for column in _DESCRIPTIVE_COLUMNS],
            *[f"post_{column}" for column in _DESCRIPTIVE_COLUMNS],
            "delta_mean",
            "delta_percent",
            "change_direction",
            "t_test_p_value",
            "mann_whitney_p_value",
            "statistically_significant",
            "significance_alpha",
        ]
        return pd.DataFrame(rows, columns=columns)
