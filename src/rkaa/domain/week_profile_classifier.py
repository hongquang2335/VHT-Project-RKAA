"""Classify timestamps into weekday or weekend buckets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class WeekProfileClassification:
    """Represents the classified week-profile bucket for a timestamp."""

    profile: str


def classify_week_profile(timestamp: datetime) -> WeekProfileClassification:
    """Classify a timezone-normalized timestamp as weekday or weekend."""

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("Timestamp must be timezone-aware before week-profile classification.")

    profile = "weekday" if timestamp.weekday() < 5 else "weekend"
    return WeekProfileClassification(profile=profile)
