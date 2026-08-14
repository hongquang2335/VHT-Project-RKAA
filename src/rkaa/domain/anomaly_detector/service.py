"""Điều phối ba cơ chế phát hiện bất thường của FR-302."""

from __future__ import annotations

import pandas as pd

from rkaa.domain.anomaly_detector.baseline_detector import HistoricalBaselineDetector
from rkaa.domain.anomaly_detector.models import AnomalySeverity
from rkaa.domain.anomaly_detector.sigma_detector import ThreeSigmaDetector
from rkaa.domain.anomaly_detector.threshold_detector import ConfiguredThresholdDetector
from rkaa.domain.threshold_manager import ThresholdManagerService, ThresholdSeverity


class AnomalyDetectionService:
    """Kết hợp baseline lịch sử, quy tắc 3-sigma và ngưỡng cấu hình."""

    def __init__(
        self,
        threshold_manager: ThresholdManagerService,
        *,
        baseline_detector: HistoricalBaselineDetector | None = None,
        sigma_detector: ThreeSigmaDetector | None = None,
    ) -> None:
        self.baseline_detector = baseline_detector or HistoricalBaselineDetector(z_threshold=2.0)
        self.sigma_detector = sigma_detector or ThreeSigmaDetector(sigma=3.0)
        self.threshold_detector = ConfiguredThresholdDetector(threshold_manager)

    def detect(self, impact_report_df: pd.DataFrame, baseline_df: pd.DataFrame) -> pd.DataFrame:
        """Trả bảng FR-302 kèm bằng chứng và mức độ tổng hợp cho từng dòng."""

        result = self.baseline_detector.detect(impact_report_df, baseline_df)
        result = self.sigma_detector.detect(result)
        result = self.threshold_detector.detect(result)

        methods: list[str] = []
        severities: list[str] = []
        anomaly_flags: list[bool] = []
        for row in result.itertuples(index=False):
            row_methods: list[str] = []
            if bool(row.baseline_abnormal):
                row_methods.append("HISTORICAL_BASELINE_2SIGMA")
            if bool(row.three_sigma_abnormal):
                row_methods.append("THREE_SIGMA")
            if row.threshold_severity != ThresholdSeverity.NONE.value:
                row_methods.append("CONFIGURED_THRESHOLD")

            anomaly = bool(row_methods)
            if (
                bool(row.three_sigma_abnormal)
                or row.threshold_severity == ThresholdSeverity.CRITICAL.value
            ):
                severity = AnomalySeverity.CRITICAL.value
            elif anomaly:
                severity = AnomalySeverity.WARNING.value
            else:
                severity = AnomalySeverity.NORMAL.value

            methods.append("|".join(row_methods))
            severities.append(severity)
            anomaly_flags.append(anomaly)

        result["anomaly_flag"] = anomaly_flags
        result["anomaly_severity"] = severities
        result["anomaly_methods"] = methods
        return result
