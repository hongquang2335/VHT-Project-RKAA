"""Detect KPI outliers using the interquartile range rule."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

DEFAULT_IQR_MULTIPLIER = 1.5


class SupportsNumericValue(Protocol):
    """Minimal contract required for IQR outlier detection."""

    value: float


@dataclass(frozen=True, slots=True)
class IQROutlierResult:
    """Represents a detected outlier and its deviation score."""

    record_index: int
    value: float
    score: float
    reason: str


def detect_iqr_outliers(
    records: Iterable[SupportsNumericValue],
    *,
    multiplier: float = DEFAULT_IQR_MULTIPLIER,
) -> list[IQROutlierResult]:
    """Return outliers detected by Tukey's IQR fences without mutating inputs."""

    if multiplier <= 0:
        raise ValueError("multiplier must be greater than zero.")

    indexed_records = list(enumerate(records))
    if len(indexed_records) < 4:
        return []

    values = [record.value for _, record in indexed_records]
    q1 = _percentile(values, 25)
    q3 = _percentile(values, 75)
    iqr = q3 - q1
    if iqr == 0:
        return []

    lower_fence = q1 - multiplier * iqr
    upper_fence = q3 + multiplier * iqr

    outliers: list[IQROutlierResult] = []
    for index, record in indexed_records:
        if lower_fence <= record.value <= upper_fence:
            continue

        score = _calculate_outlier_score(
            value=record.value,
            lower_fence=lower_fence,
            upper_fence=upper_fence,
            iqr=iqr,
        )
        outliers.append(
            IQROutlierResult(
                record_index=index,
                value=record.value,
                score=score,
                reason="iqr_outlier",
            )
        )

    return outliers


def _percentile(values: list[float], percentile: int) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]

    rank = (len(ordered) - 1) * (percentile / 100)
    lower_index = int(rank)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    fraction = rank - lower_index

    lower_value = ordered[lower_index]
    upper_value = ordered[upper_index]
    return lower_value + (upper_value - lower_value) * fraction


def _calculate_outlier_score(
    *,
    value: float,
    lower_fence: float,
    upper_fence: float,
    iqr: float,
) -> float:
    if value < lower_fence:
        return (lower_fence - value) / iqr

    return (value - upper_fence) / iqr
