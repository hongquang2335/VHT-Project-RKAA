"""Assess whether a baseline has enough clean history to be reliable."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol

from rkaa.core.config import ConfigError, load_settings

DEFAULT_REQUIRED_CLEAN_DAYS = 14


class SupportsStartTime(Protocol):
    """Minimal clean-sample contract required for baseline confidence checks."""

    start_time: datetime


@dataclass(frozen=True, slots=True)
class BaselineConfidenceAssessment:
    """Represents the confidence status of a baseline history window."""

    status: str
    clean_day_count: int
    required_day_count: int
    is_reliable: bool


def assess_baseline_confidence(
    records: Iterable[SupportsStartTime],
    *,
    required_clean_days: int | None = None,
) -> BaselineConfidenceAssessment:
    """Classify baseline history as insufficient or reliable based on clean-day coverage."""

    resolved_required_days = _resolve_required_clean_days(required_clean_days)
    clean_days = {record.start_time.date() for record in records}

    clean_day_count = len(clean_days)
    is_reliable = clean_day_count >= resolved_required_days
    return BaselineConfidenceAssessment(
        status="reliable" if is_reliable else "insufficient",
        clean_day_count=clean_day_count,
        required_day_count=resolved_required_days,
        is_reliable=is_reliable,
    )


def _resolve_required_clean_days(required_clean_days: int | None) -> int:
    if required_clean_days is not None:
        _validate_required_clean_days(required_clean_days)
        return required_clean_days

    try:
        resolved = load_settings().app.baseline_min_clean_days
    except ConfigError:
        return DEFAULT_REQUIRED_CLEAN_DAYS

    _validate_required_clean_days(resolved)
    return resolved


def _validate_required_clean_days(required_clean_days: int) -> None:
    if required_clean_days <= 0:
        raise ValueError("required_clean_days must be a positive integer.")
