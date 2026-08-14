"""Áp dụng quy tắc 3-sigma cho FR-302."""

from __future__ import annotations

import pandas as pd


class ThreeSigmaDetector:
    """Gắn cờ khi trung bình sau tác động cách trung bình baseline lịch sử ít nhất 3 sigma."""

    def __init__(self, *, sigma: float = 3.0) -> None:
        if sigma <= 0:
            raise ValueError("sigma phải > 0")
        self.sigma = float(sigma)

    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        if "historical_z_score" not in df.columns:
            raise ValueError("Cần historical_z_score trước khi chạy 3-sigma detector")
        result = df.copy()
        z_score = pd.to_numeric(result["historical_z_score"], errors="coerce")
        result["three_sigma_abnormal"] = (z_score >= self.sigma).fillna(False)
        result["three_sigma_threshold"] = self.sigma
        return result
