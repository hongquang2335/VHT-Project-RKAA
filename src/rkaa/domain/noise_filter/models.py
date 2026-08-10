"""Mô hình cấu hình và kết quả cho FR-201."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd


@dataclass(frozen=True, slots=True)
class NullSentinelConfig:
    enabled: bool = True
    global_values: tuple[float, ...] = ()
    per_kpi: dict[str, tuple[float, ...]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ImpactWindowConfig:
    enabled: bool = True
    excluded_impact_types: tuple[str, ...] = ()
    match_mode: str = "exact_or_prefix"


@dataclass(frozen=True, slots=True)
class RestartConfig:
    enabled: bool = False
    eligible_metrics: tuple[str, ...] = ()
    reset_max_value: float = 100.0
    min_previous_value: float = 1000.0
    min_drop_ratio: float = 0.90
    confirmation_points: int = 2
    concurrent_window_minutes: int = 15
    min_concurrent_counters: int = 2
    post_restart_grace_minutes: int = 15


@dataclass(frozen=True, slots=True)
class IQRConfig:
    enabled: bool = True
    multiplier: float = 1.5
    min_samples: int = 24
    insufficient_samples: str = "skip"
    zero_iqr: str = "skip"


@dataclass(frozen=True, slots=True)
class ZScoreConfig:
    enabled: bool = False
    threshold: float = 3.0
    min_samples: int = 100
    insufficient_samples: str = "skip"
    zero_std: str = "skip"


@dataclass(frozen=True, slots=True)
class StatisticalOutlierConfig:
    enabled: bool = True
    combination: str = "any"
    iqr: IQRConfig = field(default_factory=IQRConfig)
    z_score: ZScoreConfig = field(default_factory=ZScoreConfig)


@dataclass(frozen=True, slots=True)
class RangeRule:
    min_value: float | None = None
    max_value: float | None = None


@dataclass(frozen=True, slots=True)
class CustomRuleConfig:
    enabled: bool = True
    rules: dict[str, RangeRule] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NoiseFilterConfig:
    null_sentinel: NullSentinelConfig = field(default_factory=NullSentinelConfig)
    impact_window: ImpactWindowConfig = field(default_factory=ImpactWindowConfig)
    restart: RestartConfig = field(default_factory=RestartConfig)
    statistical_outlier: StatisticalOutlierConfig = field(
        default_factory=StatisticalOutlierConfig
    )
    custom_rule: CustomRuleConfig = field(default_factory=CustomRuleConfig)


@dataclass(frozen=True, slots=True)
class ExclusionWindow:
    """Khoảng thời gian không dùng cho baseline của một NE.

    ``t2_utc=None`` biểu diễn sự kiện vẫn đang diễn ra.
    """

    ne_id: str
    t1_utc: datetime
    t2_utc: datetime | None
    reason: str
    source: str


@dataclass(slots=True)
class FilterOutcome:
    """Kết quả của một bước lọc riêng lẻ."""

    cleaned_df: pd.DataFrame
    excluded_df: pd.DataFrame
    summary: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CleanResult:
    """Kết quả cuối FR-201.

    ``cleaned_df`` chứa dữ liệu còn được dùng cho phân tích tiếp theo.
    ``excluded_df`` chứa dữ liệu đã bị loại cùng nguyên nhân loại.
    """

    cleaned_df: pd.DataFrame
    excluded_df: pd.DataFrame
    summary: dict[str, Any] = field(default_factory=dict)
