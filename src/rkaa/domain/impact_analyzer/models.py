"""Mô hình domain cho phân tích tác động FR-301."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd


class ImpactTrendAssessment(StrEnum):
    """Đánh giá xu hướng KPI sau tác động."""

    IMPROVED = "IMPROVED"
    DEGRADED = "DEGRADED"
    UNCHANGED = "UNCHANGED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INFORMATIONAL = "INFORMATIONAL"


@dataclass(slots=True)
class ImpactAnalysisResult:
    """Kết quả FR-301 gồm hai cửa sổ và bảng so sánh."""

    pre_df: pd.DataFrame
    post_df: pd.DataFrame
    report_df: pd.DataFrame
