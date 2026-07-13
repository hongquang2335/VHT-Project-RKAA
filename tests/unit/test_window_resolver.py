from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from rkaa.domain.window_resolver import (
    ResolvedImpactWindows,
    TimeWindow,
    resolve_impact_windows,
)


def test_resolve_impact_windows_uses_br03_default_extension() -> None:
    result = resolve_impact_windows(
        t1=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        t2=datetime(2026, 7, 8, 11, 0, tzinfo=UTC),
        pre_window_hours=4,
        post_window_hours=3,
        recovery_buffer_hours=2,
    )

    assert result == ResolvedImpactWindows(
        pre_window=TimeWindow(
            start=datetime(2026, 7, 8, 6, 0, tzinfo=UTC),
            end=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        ),
        impact_window=TimeWindow(
            start=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
            end=datetime(2026, 7, 8, 13, 0, tzinfo=UTC),
        ),
        recovery_window=TimeWindow(
            start=datetime(2026, 7, 8, 13, 0, tzinfo=UTC),
            end=datetime(2026, 7, 8, 15, 0, tzinfo=UTC),
        ),
        post_window=TimeWindow(
            start=datetime(2026, 7, 8, 15, 0, tzinfo=UTC),
            end=datetime(2026, 7, 8, 18, 0, tzinfo=UTC),
        ),
    )


def test_resolve_impact_windows_supports_ongoing_event_with_null_t2() -> None:
    t1 = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)

    result = resolve_impact_windows(
        t1=t1,
        t2=None,
        pre_window_hours=2,
        recovery_buffer_hours=1,
    )

    assert result.impact_window == TimeWindow(
        start=t1,
        end=t1 + timedelta(hours=2),
    )


def test_resolve_impact_windows_rejects_invalid_post_window_range() -> None:
    with pytest.raises(ValueError, match="post_window_hours must be between 1 and 24"):
        resolve_impact_windows(
            t1=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
            t2=None,
            pre_window_hours=2,
            post_window_hours=25,
            recovery_buffer_hours=1,
        )


def test_resolve_impact_windows_rejects_t2_before_t1() -> None:
    with pytest.raises(ValueError, match="t2 must be greater than or equal to t1"):
        resolve_impact_windows(
            t1=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
            t2=datetime(2026, 7, 8, 9, 59, tzinfo=UTC),
            pre_window_hours=2,
            recovery_buffer_hours=1,
        )
