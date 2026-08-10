"""Giao diện chung cho các bước lọc FR-201."""

from __future__ import annotations

from typing import Protocol

import pandas as pd

from rkaa.domain.noise_filter.models import FilterOutcome


class NoiseFilterRule(Protocol):
    def apply(self, df: pd.DataFrame) -> FilterOutcome:
        """Lọc DataFrame và trả dữ liệu giữ lại cùng dữ liệu bị loại."""
