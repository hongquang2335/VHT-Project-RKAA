"""Perform a basic additive STL-like decomposition for KPI time series."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol


class SupportsTimeSeriesPoint(Protocol):
    """Minimal sample contract required for additive decomposition."""

    start_time: datetime
    value: float


@dataclass(frozen=True, slots=True)
class STLDecompositionResult:
    """Additive decomposition components aligned to ordered samples."""

    timestamps: list[datetime]
    observed: list[float]
    trend: list[float]
    seasonal: list[float]
    residual: list[float]


def decompose_stl(
    samples: Iterable[SupportsTimeSeriesPoint],
    *,
    season_length: int,
) -> STLDecompositionResult:
    """Split a KPI series into trend, seasonal, and residual components."""

    if season_length <= 1:
        raise ValueError("season_length must be greater than 1.")

    ordered_samples = sorted(samples, key=lambda sample: sample.start_time)
    if len(ordered_samples) < season_length:
        raise ValueError("samples must contain at least one full season.")

    timestamps = [sample.start_time for sample in ordered_samples]
    observed = [sample.value for sample in ordered_samples]
    trend = _moving_average_trend(observed, window=season_length)
    detrended = [value - trend_value for value, trend_value in zip(observed, trend)]

    seasonal_pattern = _seasonal_pattern(detrended, season_length=season_length)
    seasonal = [seasonal_pattern[index % season_length] for index in range(len(observed))]
    residual = [
        value - trend_value - seasonal_value
        for value, trend_value, seasonal_value in zip(observed, trend, seasonal)
    ]

    return STLDecompositionResult(
        timestamps=timestamps,
        observed=observed,
        trend=trend,
        seasonal=seasonal,
        residual=residual,
    )


def _moving_average_trend(values: list[float], *, window: int) -> list[float]:
    radius = window // 2
    trend: list[float] = []

    for index in range(len(values)):
        start = max(0, index - radius)
        end = min(len(values), index + radius + 1)
        window_values = values[start:end]
        trend.append(sum(window_values) / len(window_values))

    return trend


def _seasonal_pattern(detrended: list[float], *, season_length: int) -> list[float]:
    seasonal_groups: list[list[float]] = [[] for _ in range(season_length)]

    for index, value in enumerate(detrended):
        seasonal_groups[index % season_length].append(value)

    pattern = [sum(group) / len(group) for group in seasonal_groups]
    pattern_mean = sum(pattern) / len(pattern)
    return [value - pattern_mean for value in pattern]
