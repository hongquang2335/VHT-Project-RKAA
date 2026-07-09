"""Compute summary statistics for clean baseline KPI values."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median, pstdev
from typing import Iterable


@dataclass(frozen=True, slots=True)
class BaselineStatistics:
    """Represents aggregate statistics for a clean KPI sample set."""

    mean: float
    median: float
    std: float
    p5: float
    p95: float
    sample_count: int


def compute_baseline_statistics(values: Iterable[float]) -> BaselineStatistics:
    """Compute summary statistics for clean numeric baseline values."""

    ordered_values = sorted(values)
    if not ordered_values:
        raise ValueError("values must contain at least one sample.")

    return BaselineStatistics(
        mean=mean(ordered_values),
        median=median(ordered_values),
        std=pstdev(ordered_values),
        p5=_percentile(ordered_values, 5),
        p95=_percentile(ordered_values, 95),
        sample_count=len(ordered_values),
    )


def _percentile(sorted_values: list[float], percentile: int) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]

    rank = (len(sorted_values) - 1) * (percentile / 100)
    lower_index = int(rank)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = rank - lower_index

    lower_value = sorted_values[lower_index]
    upper_value = sorted_values[upper_index]
    return lower_value + (upper_value - lower_value) * fraction
