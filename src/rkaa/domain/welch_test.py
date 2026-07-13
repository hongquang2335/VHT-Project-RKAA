"""Run Welch's t-test for two independent KPI sample sets."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import fmean, variance
from typing import Iterable, Protocol


DEFAULT_ALPHA = 0.05


class SupportsNumericValue(Protocol):
    """Minimal sample contract required for Welch's t-test."""

    value: float


@dataclass(frozen=True, slots=True)
class WelchTestResult:
    """Outcome of Welch's t-test for two independent samples."""

    statistic: float
    p_value: float
    is_significant: bool


def run_welch_t_test(
    *,
    pre_samples: Iterable[SupportsNumericValue],
    post_samples: Iterable[SupportsNumericValue],
    alpha: float = DEFAULT_ALPHA,
) -> WelchTestResult:
    """Compute Welch's t-test statistic and two-tailed p-value."""

    _validate_alpha(alpha)

    pre_values = [sample.value for sample in pre_samples]
    post_values = [sample.value for sample in post_samples]
    _validate_sample_sizes(pre_values=pre_values, post_values=post_values)

    pre_mean = fmean(pre_values)
    post_mean = fmean(post_values)
    pre_variance = variance(pre_values)
    post_variance = variance(post_values)

    standard_error_squared = (pre_variance / len(pre_values)) + (post_variance / len(post_values))
    if standard_error_squared == 0:
        if pre_mean == post_mean:
            p_value = 1.0
            statistic = 0.0
        else:
            p_value = 0.0
            statistic = math.inf if post_mean > pre_mean else -math.inf

        return WelchTestResult(
            statistic=statistic,
            p_value=p_value,
            is_significant=p_value < alpha,
        )

    statistic = (post_mean - pre_mean) / math.sqrt(standard_error_squared)
    degrees_of_freedom = _welch_satterthwaite_df(
        pre_variance=pre_variance,
        post_variance=post_variance,
        pre_size=len(pre_values),
        post_size=len(post_values),
    )
    p_value = _two_tailed_p_value(statistic=statistic, degrees_of_freedom=degrees_of_freedom)

    return WelchTestResult(
        statistic=statistic,
        p_value=p_value,
        is_significant=p_value < alpha,
    )


def _validate_alpha(alpha: float) -> None:
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1.")


def _validate_sample_sizes(
    *,
    pre_values: list[float],
    post_values: list[float],
) -> None:
    if len(pre_values) < 2:
        raise ValueError("pre_samples must contain at least two values.")
    if len(post_values) < 2:
        raise ValueError("post_samples must contain at least two values.")


def _welch_satterthwaite_df(
    *,
    pre_variance: float,
    post_variance: float,
    pre_size: int,
    post_size: int,
) -> float:
    left = pre_variance / pre_size
    right = post_variance / post_size
    numerator = (left + right) ** 2
    denominator = ((left**2) / (pre_size - 1)) + ((right**2) / (post_size - 1))

    if denominator == 0:
        return math.inf
    return numerator / denominator


def _two_tailed_p_value(*, statistic: float, degrees_of_freedom: float) -> float:
    absolute_t = abs(statistic)
    if absolute_t == math.inf:
        return 0.0
    if degrees_of_freedom == math.inf:
        return math.erfc(absolute_t / math.sqrt(2))

    x = degrees_of_freedom / (degrees_of_freedom + absolute_t**2)
    return _regularized_incomplete_beta(
        x=x,
        a=degrees_of_freedom / 2,
        b=0.5,
    )


def _regularized_incomplete_beta(*, x: float, a: float, b: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0

    log_beta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp((a * math.log(x)) + (b * math.log1p(-x)) + log_beta)

    if x < (a + 1) / (a + b + 2):
        return front * _beta_continued_fraction(x=x, a=a, b=b) / a

    return 1 - (front * _beta_continued_fraction(x=1 - x, a=b, b=a) / b)


def _beta_continued_fraction(*, x: float, a: float, b: float) -> float:
    max_iterations = 200
    epsilon = 3e-14
    fpmin = 1e-300

    qab = a + b
    qap = a + 1
    qam = a - 1

    c = 1.0
    d = 1.0 - (qab * x / qap)
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    result = d

    for iteration in range(1, max_iterations + 1):
        even_index = 2 * iteration

        numerator = (
            iteration
            * (b - iteration)
            * x
            / ((qam + even_index) * (a + even_index))
        )
        d = 1.0 + (numerator * d)
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + (numerator / c)
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        result *= d * c

        numerator = (
            -((a + iteration) * (qab + iteration) * x)
            / ((a + even_index) * (qap + even_index))
        )
        d = 1.0 + (numerator * d)
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + (numerator / c)
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d

        delta = d * c
        result *= delta
        if abs(delta - 1.0) < epsilon:
            break

    return result
