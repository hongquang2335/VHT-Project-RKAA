"""Mô hình domain cho các phép thống kê của FR-301."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ChangeDirection(StrEnum):
    """Chiều thay đổi của giá trị sau tác động so với trước tác động."""

    INCREASE = "INCREASE"
    DECREASE = "DECREASE"
    UNCHANGED = "UNCHANGED"


@dataclass(frozen=True, slots=True)
class StatisticalTestConfig:
    """Cấu hình kiểm định thống kê dùng khi so sánh hai cửa sổ."""

    alpha: float = 0.05

    def __post_init__(self) -> None:
        if not 0.0 < self.alpha < 1.0:
            raise ValueError("alpha phải nằm trong khoảng (0, 1)")
