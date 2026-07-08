"""Impact event persistence model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from rkaa.infrastructure.data_store.base import Base


class ImpactEvent(Base):
    """Represents a suspected or confirmed network impact event."""

    __tablename__ = "impact_events"
    __table_args__ = (
        CheckConstraint(
            "source IN ('manual', 'cli', 'imported')",
            name="ck_impact_events_source",
        ),
        CheckConstraint(
            "status IN ('draft', 'confirmed', 'analyzed', 'cancelled')",
            name="ck_impact_events_status",
        ),
        CheckConstraint(
            "t2 IS NULL OR t2 > t1",
            name="ck_impact_events_t2_after_t1",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ne_id: Mapped[str] = mapped_column(String(64), nullable=False)
    t1: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    t2: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    impact_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
