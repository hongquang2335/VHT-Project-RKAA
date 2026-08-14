"""Mô hình domain cho phát hiện bất thường sau tác động FR-302."""

from __future__ import annotations

from enum import StrEnum


class AnomalySeverity(StrEnum):
    """Mức tổng hợp của một bất thường sau tác động."""

    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
