from __future__ import annotations

from dataclasses import dataclass

import pytest

from rkaa.domain.impact_classifier import (
    ImpactClassificationResult,
    classify_impact,
)


@dataclass(frozen=True, slots=True)
class KPIDefinitionStub:
    direction_preference: str


def test_classify_impact_returns_insufficient_data_first() -> None:
    result = classify_impact(
        kpi_definition=KPIDefinitionStub(direction_preference="higher_is_better"),
        delta_abs=10.0,
        is_significant=True,
        has_sufficient_data=False,
    )

    assert result == ImpactClassificationResult(classification="insufficient_data")


def test_classify_impact_returns_stable_when_not_significant() -> None:
    result = classify_impact(
        kpi_definition=KPIDefinitionStub(direction_preference="higher_is_better"),
        delta_abs=-5.0,
        is_significant=False,
        has_sufficient_data=True,
    )

    assert result == ImpactClassificationResult(classification="stable")


def test_classify_impact_uses_higher_is_better_for_positive_delta() -> None:
    result = classify_impact(
        kpi_definition=KPIDefinitionStub(direction_preference="higher_is_better"),
        delta_abs=3.5,
        is_significant=True,
        has_sufficient_data=True,
    )

    assert result == ImpactClassificationResult(classification="improved")


def test_classify_impact_uses_higher_is_better_for_negative_delta() -> None:
    result = classify_impact(
        kpi_definition=KPIDefinitionStub(direction_preference="higher_is_better"),
        delta_abs=-3.5,
        is_significant=True,
        has_sufficient_data=True,
    )

    assert result == ImpactClassificationResult(classification="degraded")


def test_classify_impact_uses_lower_is_better_for_negative_delta() -> None:
    result = classify_impact(
        kpi_definition=KPIDefinitionStub(direction_preference="lower_is_better"),
        delta_abs=-2.0,
        is_significant=True,
        has_sufficient_data=True,
    )

    assert result == ImpactClassificationResult(classification="improved")


def test_classify_impact_uses_lower_is_better_for_positive_delta() -> None:
    result = classify_impact(
        kpi_definition=KPIDefinitionStub(direction_preference="lower_is_better"),
        delta_abs=2.0,
        is_significant=True,
        has_sufficient_data=True,
    )

    assert result == ImpactClassificationResult(classification="degraded")


def test_classify_impact_keeps_context_dependent_as_stable() -> None:
    result = classify_impact(
        kpi_definition=KPIDefinitionStub(direction_preference="context_dependent"),
        delta_abs=8.0,
        is_significant=True,
        has_sufficient_data=True,
    )

    assert result == ImpactClassificationResult(classification="stable")


def test_classify_impact_rejects_unknown_direction_preference() -> None:
    with pytest.raises(ValueError, match="Unsupported direction_preference 'invalid'."):
        classify_impact(
            kpi_definition=KPIDefinitionStub(direction_preference="invalid"),
            delta_abs=1.0,
            is_significant=True,
            has_sufficient_data=True,
        )
