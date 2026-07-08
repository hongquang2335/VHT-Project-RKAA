from __future__ import annotations

from dataclasses import dataclass

import pytest

from rkaa.domain.noise_filter.iqr_outlier_filter import (
    IQROutlierResult,
    detect_iqr_outliers,
)


@dataclass(frozen=True, slots=True)
class KPIValuePoint:
    value: float


def _make_points(*values: float) -> list[KPIValuePoint]:
    return [KPIValuePoint(value=value) for value in values]


def test_detect_iqr_outliers_returns_empty_for_small_samples() -> None:
    records = _make_points(10.0, 11.0, 12.0)

    assert detect_iqr_outliers(records) == []


def test_detect_iqr_outliers_returns_empty_when_iqr_is_zero() -> None:
    records = _make_points(10.0, 10.0, 10.0, 10.0, 10.0)

    assert detect_iqr_outliers(records) == []


def test_detect_iqr_outliers_flags_high_outlier_with_score() -> None:
    records = _make_points(10.0, 11.0, 12.0, 13.0, 100.0)

    assert detect_iqr_outliers(records) == [
        IQROutlierResult(
            record_index=4,
            value=100.0,
            score=42.0,
            reason="iqr_outlier",
        )
    ]


def test_detect_iqr_outliers_flags_low_outlier_with_score() -> None:
    records = _make_points(-50.0, 10.0, 11.0, 12.0, 13.0)

    assert detect_iqr_outliers(records) == [
        IQROutlierResult(
            record_index=0,
            value=-50.0,
            score=28.5,
            reason="iqr_outlier",
        )
    ]


def test_detect_iqr_outliers_respects_custom_multiplier() -> None:
    records = _make_points(10.0, 11.0, 12.0, 13.0, 20.0)

    assert detect_iqr_outliers(records, multiplier=1.0) == [
        IQROutlierResult(
            record_index=4,
            value=20.0,
            score=2.5,
            reason="iqr_outlier",
        )
    ]


def test_detect_iqr_outliers_rejects_non_positive_multiplier() -> None:
    with pytest.raises(ValueError, match="multiplier must be greater than zero"):
        detect_iqr_outliers(_make_points(10.0, 11.0, 12.0, 13.0), multiplier=0)
