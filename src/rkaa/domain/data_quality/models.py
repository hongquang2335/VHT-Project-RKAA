"""Mô hình cấu hình và kết quả FR-203."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(frozen=True, slots=True)
class NormalizationConfig:
    enabled: bool = True
    assume_naive_timezone: str = "UTC"


@dataclass(frozen=True, slots=True)
class DuplicateConfig:
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class GapConfig:
    enabled: bool = True
    expected_interval_minutes: int = 15
    warning_threshold_minutes: int = 120


@dataclass(frozen=True, slots=True)
class QualityRangeRule:
    min_value: float | None = None
    max_value: float | None = None


@dataclass(frozen=True, slots=True)
class RangeValidationConfig:
    enabled: bool = True
    rules: dict[str, QualityRangeRule] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LocalSpikeConfig:
    enabled: bool = True
    window_samples: int = 96
    min_samples: int = 24
    robust_z_threshold: float = 6.0


@dataclass(frozen=True, slots=True)
class DataQualityConfig:
    normalization: NormalizationConfig = field(default_factory=NormalizationConfig)
    duplicate: DuplicateConfig = field(default_factory=DuplicateConfig)
    gap: GapConfig = field(default_factory=GapConfig)
    range_validation: RangeValidationConfig = field(default_factory=RangeValidationConfig)
    local_spike: LocalSpikeConfig = field(default_factory=LocalSpikeConfig)


@dataclass(frozen=True, slots=True)
class DataQualityIssue:
    issue_type: str
    severity: str
    row_index: int | None
    ne_id: str | None
    cell_id: str | None
    kpi_name: str | None
    timestamp: object
    period_end: object
    value: object
    detail: str


@dataclass(slots=True)
class DataQualityResult:
    """Kết quả FR-203.

    ``quality_df`` là dữ liệu đã chuẩn hóa cấu trúc và loại duplicate exact an
    toàn. ``issues_df`` là từng vấn đề phát hiện được; ``summary_df`` là báo cáo
    tổng hợp để lưu CSV sau mỗi chu kỳ.
    """

    quality_df: pd.DataFrame
    issues_df: pd.DataFrame
    summary_df: pd.DataFrame
    summary: dict[str, Any] = field(default_factory=dict)
