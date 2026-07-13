"""Run Mann-Whitney U test for two independent KPI sample sets."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Protocol


DEFAULT_ALPHA = 0.05


class SupportsNumericValue(Protocol):
    """Minimal sample contract required for Mann-Whitney U test."""

    value: float


@dataclass(frozen=True, slots=True)
class MannWhitneyUTestResult:
    """Outcome of Mann-Whitney U test for two independent samples."""

    statistic: float
    p_value: float
    is_significant: bool


def run_mann_whitney_u_test(
    *,
    pre_samples: Iterable[SupportsNumericValue],
    post_samples: Iterable[SupportsNumericValue],
    alpha: float = DEFAULT_ALPHA,
) -> MannWhitneyUTestResult:
    """Compute the Mann-Whitney U statistic and two-tailed p-value."""

    _validate_alpha(alpha)

    pre_values = [sample.value for sample in pre_samples]
    post_values = [sample.value for sample in post_samples]
    _validate_sample_sizes(pre_values=pre_values, post_values=post_values)

    combined = sorted(
        [(value, 0) for value in pre_values] + [(value, 1) for value in post_values],
        key=lambda item: item[0],
    )
    ranks, tie_groups = _average_ranks(combined)

    rank_sum_pre = sum(rank for rank, (_, group_id) in zip(ranks, combined) if group_id == 0)
    pre_size = len(pre_values)
    post_size = len(post_values)
    u_pre = rank_sum_pre - (pre_size * (pre_size + 1) / 2)
    u_post = pre_size * post_size - u_pre
    statistic = min(u_pre, u_post)

    mean_u = pre_size * post_size / 2
    std_u = _u_standard_deviation(
        pre_size=pre_size,
        post_size=post_size,
        tie_groups=tie_groups,
    )

    if std_u == 0:
        p_value = 1.0
    else:
        continuity = 0.5 if statistic != mean_u else 0.0
        z_score = (abs(statistic - mean_u) - continuity) / std_u
        p_value = math.erfc(z_score / math.sqrt(2))

    return MannWhitneyUTestResult(
        statistic=statistic,
        p_value=p_value,
        is_significant=p_value < alpha,
    )


def _validate_alpha(alpha: float) -> None:
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1.")


def _validate_sample_sizes(*, pre_values: list[float], post_values: list[float]) -> None:
    if not pre_values:
        raise ValueError("pre_samples must contain at least one value.")
    if not post_values:
        raise ValueError("post_samples must contain at least one value.")


def _average_ranks(combined: list[tuple[float, int]]) -> tuple[list[float], list[int]]:
    ranks = [0.0] * len(combined)
    tie_groups: list[int] = []
    index = 0

    while index < len(combined):
        end = index + 1
        while end < len(combined) and combined[end][0] == combined[index][0]:
            end += 1

        average_rank = (index + 1 + end) / 2
        for rank_index in range(index, end):
            ranks[rank_index] = average_rank

        tie_groups.append(end - index)
        index = end

    return ranks, tie_groups


def _u_standard_deviation(
    *,
    pre_size: int,
    post_size: int,
    tie_groups: list[int],
) -> float:
    total = pre_size + post_size
    tie_adjustment = sum(group_size**3 - group_size for group_size in tie_groups)
    variance = (
        pre_size
        * post_size
        / 12
        * ((total + 1) - (tie_adjustment / (total * (total - 1))))
    )

    if variance <= 0:
        return 0.0
    return math.sqrt(variance)
