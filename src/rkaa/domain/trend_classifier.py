"""Classify KPI trend direction from linear regression metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

MIN_CLEAR_R_SQUARED = 0.5


class SupportsTrendClassification(Protocol):
    """Minimal trend metrics contract required for trend classification."""

    slope: float
    r_squared: float


class SupportsKPIDefinition(Protocol):
    """Minimal KPI definition contract required for trend classification."""

    direction_preference: str


@dataclass(frozen=True, slots=True)
class TrendClassificationResult:
    """Final trend classification for one KPI series."""

    classification: str


def classify_trend(
    *,
    trend: SupportsTrendClassification,
    kpi_definition: SupportsKPIDefinition,
) -> TrendClassificationResult:
    """Classify a KPI trend as improving, degrading, stable, or unclear."""

    direction_preference = kpi_definition.direction_preference
    if direction_preference not in {
        "higher_is_better",
        "lower_is_better",
        "context_dependent",
    }:
        raise ValueError(f"Unsupported direction_preference '{direction_preference}'.")

    if trend.r_squared < MIN_CLEAR_R_SQUARED:
        return TrendClassificationResult(classification="unclear")

    if trend.slope == 0 or direction_preference == "context_dependent":
        return TrendClassificationResult(classification="stable")

    if direction_preference == "higher_is_better":
        classification = "improving" if trend.slope > 0 else "degrading"
    else:
        classification = "improving" if trend.slope < 0 else "degrading"

    return TrendClassificationResult(classification=classification)
