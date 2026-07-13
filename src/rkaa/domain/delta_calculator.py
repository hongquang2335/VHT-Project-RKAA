"""Calculate pre/post mean deltas for impact analysis."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Iterable, Protocol


class SupportsNumericValue(Protocol):
    """Minimal sample contract required for delta calculation."""

    value: float


@dataclass(frozen=True, slots=True)
class DeltaCalculationResult:
    """Computed delta metrics for one KPI comparison."""

    pre_mean: float
    post_mean: float
    delta_abs: float
    delta_pct: float


def calculate_delta(
    *,
    pre_samples: Iterable[SupportsNumericValue],
    post_samples: Iterable[SupportsNumericValue],
) -> DeltaCalculationResult:
    """Compute pre/post means plus absolute and percent delta."""

    pre_values = [sample.value for sample in pre_samples]
    post_values = [sample.value for sample in post_samples]

    if not pre_values:
        raise ValueError("pre_samples must contain at least one value.")
    if not post_values:
        raise ValueError("post_samples must contain at least one value.")

    pre_mean = fmean(pre_values)
    post_mean = fmean(post_values)
    delta_abs = post_mean - pre_mean
    delta_pct = 0.0 if pre_mean == 0 else (delta_abs / pre_mean) * 100

    return DeltaCalculationResult(
        pre_mean=pre_mean,
        post_mean=post_mean,
        delta_abs=delta_abs,
        delta_pct=delta_pct,
    )
