from __future__ import annotations

from dataclasses import dataclass

import pytest

from rkaa.domain.mann_whitney_test import (
    MannWhitneyUTestResult,
    run_mann_whitney_u_test,
)


@dataclass(frozen=True, slots=True)
class Sample:
    value: float


def test_run_mann_whitney_u_test_returns_expected_result_for_separated_samples() -> None:
    result = run_mann_whitney_u_test(
        pre_samples=[Sample(1.0), Sample(2.0), Sample(3.0)],
        post_samples=[Sample(7.0), Sample(8.0), Sample(9.0)],
    )

    assert result == MannWhitneyUTestResult(
        statistic=0.0,
        p_value=pytest.approx(0.08085559837005224),
        is_significant=False,
    )


def test_run_mann_whitney_u_test_handles_ties() -> None:
    result = run_mann_whitney_u_test(
        pre_samples=[Sample(1.0), Sample(2.0), Sample(2.0)],
        post_samples=[Sample(2.0), Sample(3.0), Sample(4.0)],
    )

    assert result.statistic == 1.0
    assert result.p_value == pytest.approx(0.16415972847851523)
    assert result.is_significant is False


def test_run_mann_whitney_u_test_marks_identical_samples_not_significant() -> None:
    result = run_mann_whitney_u_test(
        pre_samples=[Sample(5.0), Sample(5.0), Sample(5.0)],
        post_samples=[Sample(5.0), Sample(5.0), Sample(5.0)],
    )

    assert result == MannWhitneyUTestResult(
        statistic=4.5,
        p_value=1.0,
        is_significant=False,
    )


def test_run_mann_whitney_u_test_honors_custom_alpha() -> None:
    result = run_mann_whitney_u_test(
        pre_samples=[Sample(1.0), Sample(2.0), Sample(3.0)],
        post_samples=[Sample(7.0), Sample(8.0), Sample(9.0)],
        alpha=0.09,
    )

    assert result.p_value < 0.09
    assert result.is_significant is True


def test_run_mann_whitney_u_test_rejects_empty_pre_samples() -> None:
    with pytest.raises(ValueError, match="pre_samples must contain at least one value."):
        run_mann_whitney_u_test(
            pre_samples=[],
            post_samples=[Sample(1.0)],
        )


def test_run_mann_whitney_u_test_rejects_empty_post_samples() -> None:
    with pytest.raises(ValueError, match="post_samples must contain at least one value."):
        run_mann_whitney_u_test(
            pre_samples=[Sample(1.0)],
            post_samples=[],
        )


def test_run_mann_whitney_u_test_rejects_invalid_alpha() -> None:
    with pytest.raises(ValueError, match="alpha must be between 0 and 1."):
        run_mann_whitney_u_test(
            pre_samples=[Sample(1.0)],
            post_samples=[Sample(2.0)],
            alpha=0.0,
        )
