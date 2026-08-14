"""Áp dụng ngưỡng KPI cấu hình FR-303 vào kết quả FR-302."""

from __future__ import annotations

import math

import pandas as pd

from rkaa.domain.threshold_manager import ThresholdManagerService


class ConfiguredThresholdDetector:
    """Đánh giá delta tuyệt đối hoặc phần trăm theo policy của từng KPI."""

    def __init__(self, threshold_manager: ThresholdManagerService) -> None:
        self.threshold_manager = threshold_manager

    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        required = {"kpi_name", "delta_mean", "delta_percent"}
        missing = sorted(required.difference(df.columns))
        if missing:
            raise ValueError(f"Thiếu cột cho threshold detector: {', '.join(missing)}")

        result = df.copy()
        severities: list[str] = []
        directions: list[str | None] = []
        modes: list[str | None] = []
        thresholds: list[float | None] = []
        observed_values: list[float | None] = []

        for row in result.itertuples(index=False):
            delta_mean = float(row.delta_mean)
            raw_percent = getattr(row, "delta_percent")
            delta_percent = float(raw_percent) if pd.notna(raw_percent) else math.nan
            evaluation = self.threshold_manager.evaluate(
                str(row.kpi_name),
                delta_absolute=delta_mean,
                delta_percent=delta_percent,
            )
            severities.append(evaluation.severity.value)
            directions.append(
                None if evaluation.direction is None else evaluation.direction.value
            )
            modes.append(
                None if evaluation.matched_mode is None else evaluation.matched_mode.value
            )
            thresholds.append(evaluation.matched_threshold)
            observed_values.append(evaluation.observed_value)

        result["threshold_severity"] = severities
        result["threshold_direction"] = directions
        result["threshold_mode"] = modes
        result["threshold_value"] = thresholds
        result["threshold_observed_value"] = observed_values
        return result
