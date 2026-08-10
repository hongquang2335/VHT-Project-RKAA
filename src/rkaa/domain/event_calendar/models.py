"""Mô hình sự kiện dùng để loại baseline trong FR-202."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class BaselineExclusionEvent:
    """Khoảng event được phép loại khỏi baseline.

    Đây là model độc lập với ``noise_filter`` để event_calendar không phụ thuộc
    trực tiếp vào implementation FR-201.
    """

    event_id: str
    ne_id: str
    cell_id: str | None
    t1_utc: datetime
    t2_utc: datetime | None
    category: str
    reason: str
    description: str
