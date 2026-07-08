from __future__ import annotations

from math import nan

from rkaa.domain.noise_filter.null_filter import NoiseCheckResult, detect_null_sentinel


def test_detect_null_sentinel_flags_none_as_null_noise() -> None:
    result = detect_null_sentinel(None)

    assert result == NoiseCheckResult(is_noise=True, noise_reason="null_value")


def test_detect_null_sentinel_flags_blank_and_null_like_strings() -> None:
    blank_result = detect_null_sentinel("   ")
    text_result = detect_null_sentinel("N/A")

    assert blank_result == NoiseCheckResult(is_noise=True, noise_reason="null_value")
    assert text_result == NoiseCheckResult(is_noise=True, noise_reason="null_value")


def test_detect_null_sentinel_flags_nan_as_null_noise() -> None:
    result = detect_null_sentinel(nan)

    assert result == NoiseCheckResult(is_noise=True, noise_reason="null_value")


def test_detect_null_sentinel_flags_custom_sentinel_values() -> None:
    numeric_result = detect_null_sentinel(-9999, sentinel_values={-9999, -1111})
    string_result = detect_null_sentinel("  MISSING ", sentinel_values={"missing"})

    assert numeric_result == NoiseCheckResult(is_noise=True, noise_reason="sentinel_value")
    assert string_result == NoiseCheckResult(is_noise=True, noise_reason="sentinel_value")


def test_detect_null_sentinel_keeps_regular_values_clean() -> None:
    result = detect_null_sentinel(42.5, sentinel_values={-9999})

    assert result == NoiseCheckResult(is_noise=False, noise_reason=None)
