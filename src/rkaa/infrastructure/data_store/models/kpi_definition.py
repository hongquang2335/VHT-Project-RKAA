"""KPI definition persistence model."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from rkaa.infrastructure.data_store.base import Base


class KPIDefinition(Base):
    """Represents metadata and thresholds for a KPI."""

    __tablename__ = "kpi_definitions"
    _distinct_thresholds_check = (
        "critical_threshold IS NULL OR warning_threshold IS NULL "
        "OR critical_threshold != warning_threshold"
    )
    __table_args__ = (
        CheckConstraint(
            "direction_preference IN ('higher_is_better', 'lower_is_better', 'context_dependent')",
            name="ck_kpi_definitions_direction_preference",
        ),
        CheckConstraint(
            "data_type IN ('kpi', 'counter')",
            name="ck_kpi_definitions_data_type",
        ),
        CheckConstraint(
            _distinct_thresholds_check,
            name="ck_kpi_definitions_distinct_thresholds",
        ),
    )

    kpi_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    formula: Mapped[str | None] = mapped_column(Text, nullable=True)
    direction_preference: Mapped[str] = mapped_column(String(32), nullable=False)
    warning_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    critical_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_type: Mapped[str] = mapped_column(String(16), nullable=False)
    valid_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    valid_max: Mapped[float | None] = mapped_column(Float, nullable=True)
