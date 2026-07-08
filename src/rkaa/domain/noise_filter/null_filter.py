"""Detect null-like and sentinel KPI values."""

from __future__ import annotations

from dataclasses import dataclass
from math import isnan
from typing import Iterable

DEFAULT_NULL_STRINGS = frozenset({"", "null", "none", "n/a", "na"})


@dataclass(frozen=True, slots=True)
class NoiseCheckResult:
    """Represents whether an input value should be marked as noise."""

    is_noise: bool
    noise_reason: str | None


def detect_null_sentinel(
    value: object,
    *,
    sentinel_values: Iterable[object] = (),
    null_strings: Iterable[str] = DEFAULT_NULL_STRINGS,
) -> NoiseCheckResult:
    """Flag null-like or sentinel values without mutating the input."""

    if value is None:
        return NoiseCheckResult(is_noise=True, noise_reason="null_value")

    if isinstance(value, float) and isnan(value):
        return NoiseCheckResult(is_noise=True, noise_reason="null_value")

    if isinstance(value, str):
        normalized = value.strip()
        if normalized.casefold() in {item.strip().casefold() for item in null_strings}:
            return NoiseCheckResult(is_noise=True, noise_reason="null_value")

        value_key: object = normalized.casefold()
    else:
        value_key = value

    normalized_sentinels = {
        item.strip().casefold() if isinstance(item, str) else item for item in sentinel_values
    }
    if value_key in normalized_sentinels:
        return NoiseCheckResult(is_noise=True, noise_reason="sentinel_value")

    return NoiseCheckResult(is_noise=False, noise_reason=None)
