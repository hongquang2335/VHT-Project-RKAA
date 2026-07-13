from __future__ import annotations

import math
from dataclasses import dataclass

import pytest

from rkaa.domain.welch_test import WelchTestResult, run_welch_t_test


@dataclass(frozen=True, slots=True)
class Sample:
    value: float


def test_run_welch_t_test_returns_expected_result_for_known_sample() -> None:
    result = run_welch_t_test(
        pre_samples=[Sample(1.0), Sample(2.0)],
        post_samples=[Sample(3.0), Sample(4.0)],
    )

    assert result == WelchTestResult(
        statistic=pytest.approx(math.sqrt(8.0)),
        p_value=pytest.approx(0.10557280900008414),
        is_significant=False,
    )


def test_run_welch_t_test_marks_identical_samples_not_significant() -> None:
    result = run_welch_t_test(
        pre_samples=[Sample(5.0), Sample(5.0), Sample(5.0)],
        post_samples=[Sample(5.0), Sample(5.0), Sample(5.0)],
    )

    assert result == WelchTestResult(
        statistic=0.0,
        p_value=1.0,
        is_significant=False,
    )


def test_run_welch_t_test_marks_constant_shift_as_significant() -> None:
    result = run_welch_t_test(
        pre_samples=[Sample(1.0), Sample(1.0), Sample(1.0)],
        post_samples=[Sample(10.0), Sample(10.0), Sample(10.0)],
    )

    assert math.isinf(result.statistic)
    assert result.p_value == 0.0
    assert result.is_significant is True


def test_run_welch_t_test_honors_custom_alpha() -> None:
    result = run_welch_t_test(
        pre_samples=[Sample(1.0), Sample(2.0)],
        post_samples=[Sample(3.0), Sample(4.0)],
        alpha=0.11,
    )

    assert result.p_value < 0.11
    assert result.is_significant is True


def test_run_welch_t_test_rejects_small_pre_sample() -> None:
    with pytest.raises(ValueError, match="pre_samples must contain at least two values."):
        run_welch_t_test(
            pre_samples=[Sample(1.0)],
            post_samples=[Sample(1.0), Sample(2.0)],
        )


def test_run_welch_t_test_rejects_small_post_sample() -> None:
    with pytest.raises(ValueError, match="post_samples must contain at least two values."):
        run_welch_t_test(
            pre_samples=[Sample(1.0), Sample(2.0)],
            post_samples=[Sample(1.0)],
        )


def test_run_welch_t_test_rejects_invalid_alpha() -> None:
    with pytest.raises(ValueError, match="alpha must be between 0 and 1."):
        run_welch_t_test(
            pre_samples=[Sample(1.0), Sample(2.0)],
            post_samples=[Sample(3.0), Sample(4.0)],
            alpha=1.0,
        )
