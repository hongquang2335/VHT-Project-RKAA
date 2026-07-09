from __future__ import annotations

from datetime import UTC, datetime

import pytest

from rkaa.domain.week_profile_classifier import classify_week_profile


def test_classify_week_profile_returns_weekday_for_monday() -> None:
    timestamp = datetime(2026, 7, 6, 8, 30, tzinfo=UTC)

    result = classify_week_profile(timestamp)

    assert result.profile == "weekday"


def test_classify_week_profile_returns_weekend_for_saturday() -> None:
    timestamp = datetime(2026, 7, 11, 8, 30, tzinfo=UTC)

    result = classify_week_profile(timestamp)

    assert result.profile == "weekend"


def test_classify_week_profile_uses_the_normalized_local_day() -> None:
    timestamp = datetime.fromisoformat("2026-07-12T00:30:00+07:00")

    result = classify_week_profile(timestamp)

    assert result.profile == "weekend"


def test_classify_week_profile_rejects_naive_timestamps() -> None:
    timestamp = datetime(2026, 7, 6, 8, 30)

    with pytest.raises(ValueError, match="timezone-aware"):
        classify_week_profile(timestamp)
