"""KPI record persistence model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from rkaa.infrastructure.data_store.base import Base


class KPIRecord(Base):
    """Represents a time-bounded KPI measurement."""

    __tablename__ = "kpi_records"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_kpi_records_end_after_start"),
        UniqueConstraint(
            "ne_id",
            "kpi_name",
            "start_time",
            name="uq_kpi_records_ne_kpi_start_time",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ne_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kpi_name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    quality_flag: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_noise: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    noise_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
