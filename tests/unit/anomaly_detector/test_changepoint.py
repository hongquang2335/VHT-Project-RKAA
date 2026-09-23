from __future__ import annotations

import numpy as np
import pandas as pd

from rkaa.domain.anomaly_detector import ChangePointConfig, ChangePointDetector


def _components(values: np.ndarray, residual: np.ndarray | None = None) -> pd.DataFrame:
    residual_values = np.zeros_like(values) if residual is None else residual
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(
                "2026-01-01", periods=len(values), freq="h", tz="UTC"
            ),
            "ne_id": "NE1",
            "cell_id": "CELL1",
            "kpi_name": "KPI",
            "trend": values,
            "residual": residual_values,
        }
    )


def test_pelt_detects_level_shift_within_two_periods() -> None:
    values = np.r_[np.zeros(120), np.ones(120) * 5.0]
    detector = ChangePointDetector(
        ChangePointConfig(
            penalty_scale=4.0,
            minimum_segment_points=12,
            detect_variance=False,
        )
    )
    result = detector.detect(_components(values))
    level = result[result["change_type"].str.contains("LEVEL")]
    assert not level.empty
    assert int((level["change_index"] - 120).abs().min()) <= 2


def test_pelt_can_flag_residual_variance_change() -> None:
    rng = np.random.default_rng(7)
    residual = np.r_[rng.normal(0, 0.1, 160), rng.normal(0, 2.0, 160)]
    values = np.zeros_like(residual)
    detector = ChangePointDetector(
        ChangePointConfig(
            penalty_scale=4.0,
            minimum_segment_points=16,
            detect_variance=True,
        )
    )
    result = detector.detect(_components(values, residual))
    variance = result[result["change_type"].str.contains("VARIANCE")]
    assert not variance.empty
    assert int((variance["change_index"] - 160).abs().min()) <= 2


def test_fr405_change_point_rows_are_engineer_review_alerts() -> None:
    values = np.r_[np.zeros(120), np.ones(120) * 5.0]
    detector = ChangePointDetector(
        ChangePointConfig(
            penalty_scale=4.0,
            minimum_segment_points=12,
            detect_variance=False,
            search_step_points=2,
            localization_tolerance_periods=2,
        )
    )
    result = detector.detect(_components(values))
    assert not result.empty
    assert set(result["algorithm"]) == {"PELT"}
    assert result["alert_required"].all()
    assert set(result["review_status"]) == {"ENGINEER_REVIEW_REQUIRED"}
    assert (result["localization_tolerance_periods"] == 2).all()


def test_fr405_empty_result_keeps_output_schema() -> None:
    detector = ChangePointDetector(ChangePointConfig(detect_variance=False))
    result = detector.detect(_components(np.zeros(240)))
    assert result.empty
    assert {
        "change_timestamp",
        "change_type",
        "alert_required",
        "review_status",
    }.issubset(result.columns)
