from __future__ import annotations

import math

from rkaa.domain.statistical_engine import StatisticalEngine


def test_describe_and_two_fr301_tests() -> None:
    engine = StatisticalEngine()
    pre = [1.0, 1.0, 2.0, 2.0, 3.0]
    post = [10.0, 11.0, 12.0, 13.0, 14.0]

    stats = engine.describe(pre)
    assert stats.count == 5
    assert stats.mean == 1.8
    assert math.isfinite(stats.std)

    welch = engine.welch_t_test(pre, post)
    mann_whitney = engine.mann_whitney_u_test(pre, post)
    assert 0 <= welch < 0.05
    assert 0 <= mann_whitney < 0.05
    assert engine.is_significant(welch, mann_whitney, alpha=0.05)
