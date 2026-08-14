"""Mô hình domain cho cấu hình ngưỡng KPI của FR-303."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ThresholdMode(StrEnum):
    """Kiểu giá trị dùng để so với ngưỡng."""

    ABSOLUTE = "ABSOLUTE"
    PERCENTAGE = "PERCENTAGE"


class ThresholdSeverity(StrEnum):
    """Mức cảnh báo do ngưỡng cấu hình tạo ra."""

    NONE = "NONE"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ThresholdDirection(StrEnum):
    """Chiều thay đổi được cấu hình ngưỡng."""

    INCREASE = "INCREASE"
    DECREASE = "DECREASE"


class DirectionPreference(StrEnum):
    """Chiều KPI được xem là tốt hơn, dùng để diễn giải FR-301."""

    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    INFORMATIONAL = "informational"


@dataclass(frozen=True, slots=True)
class ThresholdLevel:
    """Một mức warning/critical với kiểu và giá trị ngưỡng."""

    mode: ThresholdMode
    value: float

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("Giá trị threshold phải >= 0")


@dataclass(frozen=True, slots=True)
class DirectionThresholds:
    """Ngưỡng warning/critical cho một chiều tăng hoặc giảm."""

    warning: ThresholdLevel | None = None
    critical: ThresholdLevel | None = None


@dataclass(frozen=True, slots=True)
class KpiThresholdPolicy:
    """Toàn bộ cấu hình ngưỡng cho một KPI."""

    kpi_name: str
    direction_preference: DirectionPreference = DirectionPreference.INFORMATIONAL
    increase: DirectionThresholds = field(default_factory=DirectionThresholds)
    decrease: DirectionThresholds = field(default_factory=DirectionThresholds)


@dataclass(frozen=True, slots=True)
class ThresholdEvaluation:
    """Kết quả đánh giá một delta với cấu hình FR-303."""

    severity: ThresholdSeverity
    direction: ThresholdDirection | None = None
    matched_mode: ThresholdMode | None = None
    matched_threshold: float | None = None
    observed_value: float | None = None
