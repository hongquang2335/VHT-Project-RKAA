"""Compute linear trend metrics for KPI time-series samples."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol


class SupportsTrendPoint(Protocol):
    """Minimal sample contract required for linear trend calculation."""

    start_time: datetime
    value: float


@dataclass(frozen=True, slots=True)
class LinearTrendResult:
    """Regression metrics for one ordered KPI time series."""

    slope: float
    intercept: float
    r_squared: float


def calculate_linear_trend(samples: Iterable[SupportsTrendPoint]) -> LinearTrendResult:
    """Compute slope, intercept, and R-squared for KPI samples over sample order."""

    ordered_samples = sorted(samples, key=lambda sample: sample.start_time)
    if not ordered_samples:
        raise ValueError("samples must contain at least one point.")

    if len(ordered_samples) == 1:
        return LinearTrendResult(
            slope=0.0,
            intercept=ordered_samples[0].value,
            r_squared=1.0,
        )

    x_values = [float(index) for index in range(len(ordered_samples))]
    y_values = [sample.value for sample in ordered_samples]
    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)

    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
    denominator = sum((x - x_mean) ** 2 for x in x_values)
    if denominator == 0:
        slope = 0.0
    else:
        slope = numerator / denominator

    intercept = y_mean - (slope * x_mean)

    ss_tot = sum((y - y_mean) ** 2 for y in y_values)
    if ss_tot == 0:
        r_squared = 1.0
    else:
        ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(x_values, y_values))
        r_squared = 1.0 - (ss_res / ss_tot)

    return LinearTrendResult(
        slope=slope,
        intercept=intercept,
        r_squared=r_squared,
    )
