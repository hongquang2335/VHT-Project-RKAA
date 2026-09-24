"""Statistical primitives used by FR-301 impact analysis."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass(frozen=True, slots=True)
class DescriptiveStats:
    """Descriptive statistics required by FR-301."""

    count: int
    mean: float
    median: float
    std: float
    p05: float
    p95: float


class StatisticalEngine:
    """Small deterministic wrapper around the statistical tests required by FR-301."""

    @staticmethod
    def describe(values: object) -> DescriptiveStats:
        data = np.asarray(list(values), dtype=float)
        data = data[np.isfinite(data)]
        if data.size == 0:
            return DescriptiveStats(0, np.nan, np.nan, np.nan, np.nan, np.nan)
        std = float(np.std(data, ddof=1)) if data.size >= 2 else np.nan
        return DescriptiveStats(
            count=int(data.size),
            mean=float(np.mean(data)),
            median=float(np.median(data)),
            std=std,
            p05=float(np.quantile(data, 0.05)),
            p95=float(np.quantile(data, 0.95)),
        )

    @staticmethod
    def welch_t_test(pre_values: object, post_values: object) -> float:
        pre = np.asarray(list(pre_values), dtype=float)
        post = np.asarray(list(post_values), dtype=float)
        pre = pre[np.isfinite(pre)]
        post = post[np.isfinite(post)]
        if pre.size < 2 or post.size < 2:
            return np.nan
        result = stats.ttest_ind(pre, post, equal_var=False, nan_policy="omit")
        p_value = float(result.pvalue)
        return p_value if np.isfinite(p_value) else np.nan

    @staticmethod
    def mann_whitney_u_test(pre_values: object, post_values: object) -> float:
        pre = np.asarray(list(pre_values), dtype=float)
        post = np.asarray(list(post_values), dtype=float)
        pre = pre[np.isfinite(pre)]
        post = post[np.isfinite(post)]
        if pre.size == 0 or post.size == 0:
            return np.nan
        result = stats.mannwhitneyu(pre, post, alternative="two-sided", method="auto")
        p_value = float(result.pvalue)
        return p_value if np.isfinite(p_value) else np.nan

    @staticmethod
    def is_significant(*p_values: float, alpha: float = 0.05) -> bool:
        """Return True when at least one available FR-301 test rejects H0."""

        available = [float(value) for value in p_values if np.isfinite(value)]
        return bool(available) and any(value < alpha for value in available)
