"""Impact analysis persistence models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from rkaa.infrastructure.data_store.base import Base


class ImpactAnalysis(Base):
    """Represents an analysis result derived from an impact event."""

    __tablename__ = "impact_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    impact_event_id: Mapped[int] = mapped_column(
        ForeignKey("impact_events.id"),
        nullable=False,
    )
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    analysis_window: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    overall_assessment: Mapped[str] = mapped_column(String(255), nullable=False)


class KPIDelta(Base):
    """Represents KPI-level delta metrics inside an impact analysis."""

    __tablename__ = "kpi_deltas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(
        ForeignKey("impact_analyses.id"),
        nullable=False,
    )
    kpi_name: Mapped[str] = mapped_column(
        ForeignKey("kpi_definitions.kpi_name"),
        nullable=False,
    )
    pre_mean: Mapped[float] = mapped_column(Float, nullable=False)
    post_mean: Mapped[float] = mapped_column(Float, nullable=False)
    delta_abs: Mapped[float] = mapped_column(Float, nullable=False)
    delta_pct: Mapped[float] = mapped_column(Float, nullable=False)
    p_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_direction: Mapped[str] = mapped_column(String(32), nullable=False)
    anomaly_flag: Mapped[str] = mapped_column(String(32), nullable=False)
