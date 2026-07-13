from __future__ import annotations

from dataclasses import dataclass
from math import inf
from types import SimpleNamespace

import pytest

from rkaa.domain.zscore_detector import (
    DEFAULT_ZSCORE_THRESHOLD,
    ZScoreDetectionResult,
    detect_zscore_anomaly,
)


@dataclass(frozen=True, slots=True)
class BaselineStub:
    mean_value: float
    std_value: float


def test_detect_zscore_anomaly_returns_normal_within_threshold() -> None:
    result = detect_zscore_anomaly(
        value=104.0,
        baseline=BaselineStub(mean_value=100.0, std_value=2.0),
        threshold=3.0,
    )

    assert result == ZScoreDetectionResult(
        z_score=2.0,
        threshold=3.0,
        anomaly_flag="normal",
        is_anomalous=False,
    )


def test_detect_zscore_anomaly_returns_anomalous_at_threshold() -> None:
    result = detect_zscore_anomaly(
        value=106.0,
        baseline=BaselineStub(mean_value=100.0, std_value=2.0),
        threshold=3.0,
    )

    assert result == ZScoreDetectionResult(
        z_score=3.0,
        threshold=3.0,
        anomaly_flag="anomalous",
        is_anomalous=True,
    )


def test_detect_zscore_anomaly_uses_absolute_z_score() -> None:
    result = detect_zscore_anomaly(
        value=94.0,
        baseline=BaselineStub(mean_value=100.0, std_value=2.0),
        threshold=2.5,
    )

    assert result == ZScoreDetectionResult(
        z_score=-3.0,
        threshold=2.5,
        anomaly_flag="anomalous",
        is_anomalous=True,
    )


def test_detect_zscore_anomaly_reads_threshold_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "rkaa.domain.zscore_detector.load_settings",
        lambda: SimpleNamespace(app=SimpleNamespace(anomaly_zscore_threshold=2.25)),
    )

    result = detect_zscore_anomaly(
        value=104.5,
        baseline=BaselineStub(mean_value=100.0, std_value=2.0),
    )

    assert result.threshold == 2.25
    assert result.is_anomalous is True


def test_detect_zscore_anomaly_falls_back_to_default_when_config_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_config_error() -> object:
        from rkaa.core.config import ConfigError

        raise ConfigError("missing config")

    monkeypatch.setattr("rkaa.domain.zscore_detector.load_settings", _raise_config_error)

    result = detect_zscore_anomaly(
        value=104.5,
        baseline=BaselineStub(mean_value=100.0, std_value=2.0),
    )

    assert result.threshold == DEFAULT_ZSCORE_THRESHOLD
    assert result.is_anomalous is False


def test_detect_zscore_anomaly_handles_zero_std_with_equal_value() -> None:
    result = detect_zscore_anomaly(
        value=100.0,
        baseline=BaselineStub(mean_value=100.0, std_value=0.0),
        threshold=3.0,
    )

    assert result == ZScoreDetectionResult(
        z_score=0.0,
        threshold=3.0,
        anomaly_flag="normal",
        is_anomalous=False,
    )


def test_detect_zscore_anomaly_handles_zero_std_with_changed_value() -> None:
    result = detect_zscore_anomaly(
        value=101.0,
        baseline=BaselineStub(mean_value=100.0, std_value=0.0),
        threshold=3.0,
    )

    assert result == ZScoreDetectionResult(
        z_score=inf,
        threshold=3.0,
        anomaly_flag="anomalous",
        is_anomalous=True,
    )


def test_detect_zscore_anomaly_rejects_negative_std() -> None:
    with pytest.raises(ValueError, match="baseline std_value must be non-negative."):
        detect_zscore_anomaly(
            value=100.0,
            baseline=BaselineStub(mean_value=100.0, std_value=-1.0),
            threshold=3.0,
        )


def test_detect_zscore_anomaly_rejects_non_positive_threshold() -> None:
    with pytest.raises(ValueError, match="threshold must be a positive number."):
        detect_zscore_anomaly(
            value=100.0,
            baseline=BaselineStub(mean_value=100.0, std_value=1.0),
            threshold=0.0,
        )
