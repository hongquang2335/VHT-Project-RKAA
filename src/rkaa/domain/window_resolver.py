"""Resolve analysis windows around an impact event."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

DEFAULT_POST_WINDOW_HOURS = 2
MIN_POST_WINDOW_HOURS = 1
MAX_POST_WINDOW_HOURS = 24


@dataclass(frozen=True, slots=True)
class TimeWindow:
    """Represents a closed-open time window."""

    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class ResolvedImpactWindows:
    """Represents analysis windows derived from an impact event."""

    pre_window: TimeWindow
    impact_window: TimeWindow
    recovery_window: TimeWindow
    post_window: TimeWindow


def resolve_impact_windows(
    *,
    t1: datetime,
    t2: datetime | None,
    pre_window_hours: int,
    post_window_hours: int = DEFAULT_POST_WINDOW_HOURS,
    recovery_buffer_hours: int,
) -> ResolvedImpactWindows:
    """Resolve pre, impact, recovery, and post windows from impact timestamps."""

    _validate_positive_hours("pre_window_hours", pre_window_hours)
    _validate_positive_hours("recovery_buffer_hours", recovery_buffer_hours)
    _validate_post_window_hours(post_window_hours)

    impact_end = t2 or t1
    if impact_end < t1:
        raise ValueError("t2 must be greater than or equal to t1 when provided.")

    pre_window = TimeWindow(
        start=t1 - timedelta(hours=pre_window_hours),
        end=t1,
    )
    impact_window = TimeWindow(
        start=t1,
        end=impact_end + timedelta(hours=DEFAULT_POST_WINDOW_HOURS),
    )
    recovery_window = TimeWindow(
        start=impact_window.end,
        end=impact_window.end + timedelta(hours=recovery_buffer_hours),
    )
    post_window = TimeWindow(
        start=recovery_window.end,
        end=recovery_window.end + timedelta(hours=post_window_hours),
    )

    return ResolvedImpactWindows(
        pre_window=pre_window,
        impact_window=impact_window,
        recovery_window=recovery_window,
        post_window=post_window,
    )


def _validate_positive_hours(field_name: str, value: int) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")


def _validate_post_window_hours(post_window_hours: int) -> None:
    if not MIN_POST_WINDOW_HOURS <= post_window_hours <= MAX_POST_WINDOW_HOURS:
        raise ValueError(
            "post_window_hours must be between "
            f"{MIN_POST_WINDOW_HOURS} and {MAX_POST_WINDOW_HOURS}."
        )
