"""Mô hình domain cho FR-401."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd


class TemporalProfile(StrEnum):
    """Ba profile thời gian bắt buộc theo FR-401."""

    BUSY = "BUSY"
    OFF_PEAK = "OFF_PEAK"
    TRANSITION = "TRANSITION"


@dataclass(frozen=True, slots=True)
class ProfileWindow:
    """Một cửa sổ thời gian trong ngày, biểu diễn theo phút [start, end)."""

    profile: TemporalProfile
    start_minute: int
    end_minute: int

    def contains(self, minute_of_day: int) -> bool:
        """Kiểm tra phút trong ngày có thuộc cửa sổ hay không.

        Cửa sổ qua nửa đêm được hỗ trợ, ví dụ 22:00→06:00.
        """

        if self.start_minute < self.end_minute:
            return self.start_minute <= minute_of_day < self.end_minute
        return minute_of_day >= self.start_minute or minute_of_day < self.end_minute


@dataclass(frozen=True, slots=True)
class TemporalProfileConfig:
    timezone: str
    windows: tuple[ProfileWindow, ...]


@dataclass(slots=True)
class TemporalAnalysisResult:
    profiled_df: pd.DataFrame
    overlay_df: pd.DataFrame
