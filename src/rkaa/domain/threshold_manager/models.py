"""Domain models cho FR-303 KPI threshold configuration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ThresholdMode(StrEnum):
    ABSOLUTE = "absolute"
    PERCENT = "percent"


class ThresholdSeverity(StrEnum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class DirectionThreshold:
    """Ngưỡng cho một chiều tăng/giảm của KPI delta."""

    mode: ThresholdMode = ThresholdMode.ABSOLUTE
    warning: float | None = None
    critical: float | None = None

    def __post_init__(self) -> None:
        if self.warning is not None and self.warning < 0:
            raise ValueError("warning threshold phải >= 0")
        if self.critical is not None and self.critical < 0:
            raise ValueError("critical threshold phải >= 0")
        if (
            self.warning is not None
            and self.critical is not None
            and self.critical < self.warning
        ):
            raise ValueError("critical threshold phải >= warning threshold")


@dataclass(frozen=True, slots=True)
class KPIThresholdRule:
    kpi_name: str
    enabled: bool = True
    direction_preference: str = "informational"
    increase: DirectionThreshold = DirectionThreshold()
    decrease: DirectionThreshold = DirectionThreshold()

    def __post_init__(self) -> None:
        if not self.kpi_name.strip():
            raise ValueError("kpi_name không được rỗng")
        if self.direction_preference not in {
            "higher_is_better",
            "lower_is_better",
            "informational",
        }:
            raise ValueError(
                "direction_preference phải là higher_is_better/lower_is_better/informational"
            )
