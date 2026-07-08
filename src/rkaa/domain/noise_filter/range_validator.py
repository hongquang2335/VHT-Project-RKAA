"""Validate KPI values against configured definition bounds."""

from __future__ import annotations

from typing import Protocol

from rkaa.domain.noise_filter.null_filter import NoiseCheckResult


class SupportsValidRange(Protocol):
    """Minimal contract required from a KPI definition."""

    valid_min: float | None
    valid_max: float | None


def validate_value_range(
    value: float,
    kpi_definition: SupportsValidRange,
) -> NoiseCheckResult:
    """Flag values that fall outside the configured valid range."""

    valid_min = kpi_definition.valid_min
    valid_max = kpi_definition.valid_max

    if valid_min is not None and valid_max is not None and valid_min > valid_max:
        raise ValueError("KPI definition has an invalid range: valid_min cannot exceed valid_max.")

    if valid_min is not None and value < valid_min:
        return NoiseCheckResult(is_noise=True, noise_reason="below_valid_min")

    if valid_max is not None and value > valid_max:
        return NoiseCheckResult(is_noise=True, noise_reason="above_valid_max")

    return NoiseCheckResult(is_noise=False, noise_reason=None)
