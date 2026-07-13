from __future__ import annotations

from dataclasses import dataclass

import pytest

from rkaa.domain.trend_classifier import (
    MIN_CLEAR_R_SQUARED,
    TrendClassificationResult,
    classify_trend,
)


@dataclass(frozen=True, slots=True)
class TrendStub:
    slope: float
    r_squared: float


@dataclass(frozen=True, slots=True)
class KPIDefinitionStub:
    direction_preference: str


def test_classify_trend_returns_unclear_when_r_squared_is_below_threshold() -> None:
    result = classify_trend(
        trend=TrendStub(slope=5.0, r_squared=MIN_CLEAR_R_SQUARED - 0.01),
        kpi_definition=KPIDefinitionStub(direction_preference="higher_is_better"),
    )

    assert result == TrendClassificationResult(classification="unclear")


def test_classify_trend_uses_higher_is_better_for_positive_slope() -> None:
    result = classify_trend(
        trend=TrendStub(slope=1.5, r_squared=0.8),
        kpi_definition=KPIDefinitionStub(direction_preference="higher_is_better"),
    )

    assert result == TrendClassificationResult(classification="improving")


def test_classify_trend_uses_higher_is_better_for_negative_slope() -> None:
    result = classify_trend(
        trend=TrendStub(slope=-1.5, r_squared=0.8),
        kpi_definition=KPIDefinitionStub(direction_preference="higher_is_better"),
    )

    assert result == TrendClassificationResult(classification="degrading")


def test_classify_trend_uses_lower_is_better_for_negative_slope() -> None:
    result = classify_trend(
        trend=TrendStub(slope=-0.5, r_squared=0.9),
        kpi_definition=KPIDefinitionStub(direction_preference="lower_is_better"),
    )

    assert result == TrendClassificationResult(classification="improving")


def test_classify_trend_uses_lower_is_better_for_positive_slope() -> None:
    result = classify_trend(
        trend=TrendStub(slope=0.5, r_squared=0.9),
        kpi_definition=KPIDefinitionStub(direction_preference="lower_is_better"),
    )

    assert result == TrendClassificationResult(classification="degrading")


def test_classify_trend_returns_stable_for_zero_slope() -> None:
    result = classify_trend(
        trend=TrendStub(slope=0.0, r_squared=0.9),
        kpi_definition=KPIDefinitionStub(direction_preference="higher_is_better"),
    )

    assert result == TrendClassificationResult(classification="stable")


def test_classify_trend_keeps_context_dependent_as_stable() -> None:
    result = classify_trend(
        trend=TrendStub(slope=2.0, r_squared=0.9),
        kpi_definition=KPIDefinitionStub(direction_preference="context_dependent"),
    )

    assert result == TrendClassificationResult(classification="stable")


def test_classify_trend_rejects_unknown_direction_preference() -> None:
    with pytest.raises(ValueError, match="Unsupported direction_preference 'invalid'."):
        classify_trend(
            trend=TrendStub(slope=1.0, r_squared=0.9),
            kpi_definition=KPIDefinitionStub(direction_preference="invalid"),
        )
