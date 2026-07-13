"""Baseline persistence model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from rkaa.infrastructure.data_store.base import Base


class Baseline(Base):
    """Represents a persisted baseline summary for one KPI bucket."""

    __tablename__ = "baselines"
    __table_args__ = (
        UniqueConstraint(
            "ne_id",
            "kpi_name",
            "day_period",
            "week_profile",
            name="uq_baselines_group_bucket",
        ),
        CheckConstraint(
            "day_period IN ('busy', 'off_peak', 'transition')",
            name="ck_baselines_day_period",
        ),
        CheckConstraint(
            "week_profile IN ('weekday', 'weekend')",
            name="ck_baselines_week_profile",
        ),
        CheckConstraint(
            "confidence_status IN ('insufficient', 'reliable')",
            name="ck_baselines_confidence_status",
        ),
        CheckConstraint(
            "sample_count > 0",
            name="ck_baselines_sample_count_positive",
        ),
        CheckConstraint(
            "clean_day_count >= 0",
            name="ck_baselines_clean_day_count_non_negative",
        ),
        CheckConstraint(
            "required_day_count > 0",
            name="ck_baselines_required_day_count_positive",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ne_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kpi_name: Mapped[str] = mapped_column(
        ForeignKey("kpi_definitions.kpi_name"),
        nullable=False,
    )
    day_period: Mapped[str] = mapped_column(String(16), nullable=False)
    week_profile: Mapped[str] = mapped_column(String(16), nullable=False)
    mean_value: Mapped[float] = mapped_column(Float, nullable=False)
    median_value: Mapped[float] = mapped_column(Float, nullable=False)
    std_value: Mapped[float] = mapped_column(Float, nullable=False)
    p5_value: Mapped[float] = mapped_column(Float, nullable=False)
    p95_value: Mapped[float] = mapped_column(Float, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    clean_day_count: Mapped[int] = mapped_column(Integer, nullable=False)
    required_day_count: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_status: Mapped[str] = mapped_column(String(16), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
