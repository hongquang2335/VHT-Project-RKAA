from __future__ import annotations

import pytest

from rkaa.domain.noise_filter.null_filter import NoiseCheckResult
from rkaa.domain.noise_filter.range_validator import validate_value_range
from rkaa.infrastructure.data_store.models import KPIDefinition


def _make_kpi_definition(
    *,
    valid_min: float | None = 0.0,
    valid_max: float | None = 100.0,
) -> KPIDefinition:
    return KPIDefinition(
        kpi_name="availability",
        display_name="Availability",
        unit="percent",
        description="Cell availability",
        formula="available_time / total_time",
        direction_preference="higher_is_better",
        warning_threshold=98.0,
        critical_threshold=95.0,
        data_type="kpi",
        valid_min=valid_min,
        valid_max=valid_max,
    )


def test_validate_value_range_flags_value_below_minimum() -> None:
    result = validate_value_range(-0.1, _make_kpi_definition(valid_min=0.0, valid_max=100.0))

    assert result == NoiseCheckResult(is_noise=True, noise_reason="below_valid_min")


def test_validate_value_range_flags_value_above_maximum() -> None:
    result = validate_value_range(100.1, _make_kpi_definition(valid_min=0.0, valid_max=100.0))

    assert result == NoiseCheckResult(is_noise=True, noise_reason="above_valid_max")


def test_validate_value_range_accepts_value_within_bounds() -> None:
    result = validate_value_range(42.0, _make_kpi_definition(valid_min=0.0, valid_max=100.0))

    assert result == NoiseCheckResult(is_noise=False, noise_reason=None)


def test_validate_value_range_accepts_open_ended_ranges() -> None:
    lower_only = validate_value_range(5.0, _make_kpi_definition(valid_min=0.0, valid_max=None))
    upper_only = validate_value_range(5.0, _make_kpi_definition(valid_min=None, valid_max=10.0))
    unbounded = validate_value_range(5.0, _make_kpi_definition(valid_min=None, valid_max=None))

    assert lower_only == NoiseCheckResult(is_noise=False, noise_reason=None)
    assert upper_only == NoiseCheckResult(is_noise=False, noise_reason=None)
    assert unbounded == NoiseCheckResult(is_noise=False, noise_reason=None)


def test_validate_value_range_rejects_invalid_definition_range() -> None:
    with pytest.raises(ValueError, match="valid_min cannot exceed valid_max"):
        validate_value_range(50.0, _make_kpi_definition(valid_min=100.0, valid_max=0.0))
