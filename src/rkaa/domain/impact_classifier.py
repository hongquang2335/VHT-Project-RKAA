"""Classify impact outcomes from delta metrics and KPI direction preference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class SupportsKPIDefinition(Protocol):
    """Minimal KPI definition contract required for impact classification."""

    direction_preference: str


@dataclass(frozen=True, slots=True)
class ImpactClassificationResult:
    """Final classification for one KPI impact analysis."""

    classification: str


def classify_impact(
    *,
    kpi_definition: SupportsKPIDefinition,
    delta_abs: float,
    is_significant: bool,
    has_sufficient_data: bool,
) -> ImpactClassificationResult:
    """Classify a KPI impact as improved, degraded, stable, or insufficient_data."""

    if not has_sufficient_data:
        return ImpactClassificationResult(classification="insufficient_data")

    direction_preference = kpi_definition.direction_preference
    if direction_preference not in {
        "higher_is_better",
        "lower_is_better",
        "context_dependent",
    }:
        raise ValueError(f"Unsupported direction_preference '{direction_preference}'.")

    if not is_significant or delta_abs == 0:
        return ImpactClassificationResult(classification="stable")

    if direction_preference == "context_dependent":
        return ImpactClassificationResult(classification="stable")

    if direction_preference == "higher_is_better":
        classification = "improved" if delta_abs > 0 else "degraded"
    else:
        classification = "improved" if delta_abs < 0 else "degraded"

    return ImpactClassificationResult(classification=classification)
