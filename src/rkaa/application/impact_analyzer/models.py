"""Models for FR-301/FR-302 impact analysis."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImpactAnalysisConfig:
    """Core analysis settings derived from SRS business rules."""

    window_hours: int = 24
    significance_alpha: float = 0.05
    minimum_completeness: float = 0.70
    minimum_baseline_days: int = 14

    def __post_init__(self) -> None:
        if not 1 <= self.window_hours <= 24:
            raise ValueError("window_hours phải nằm trong [1, 24]")
        if not 0 < self.significance_alpha < 1:
            raise ValueError("significance_alpha phải nằm trong (0, 1)")
        if not 0 <= self.minimum_completeness <= 1:
            raise ValueError("minimum_completeness phải nằm trong [0, 1]")
        if self.minimum_baseline_days < 1:
            raise ValueError("minimum_baseline_days phải >= 1")
