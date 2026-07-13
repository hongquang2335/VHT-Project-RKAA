"""Knowledge entry persistence model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from rkaa.infrastructure.data_store.base import Base


class KnowledgeEntry(Base):
    """Represents one versioned knowledge-base entry for a KPI."""

    __tablename__ = "knowledge_entries"
    __table_args__ = (
        CheckConstraint(
            "version > 0",
            name="ck_knowledge_entries_version_positive",
        ),
        UniqueConstraint(
            "kpi_name",
            "version",
            name="uq_knowledge_entries_kpi_name_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kpi_name: Mapped[str] = mapped_column(
        ForeignKey("kpi_definitions.kpi_name"),
        nullable=False,
    )
    meaning_increase: Mapped[str] = mapped_column(Text, nullable=False)
    meaning_decrease: Mapped[str] = mapped_column(Text, nullable=False)
    common_causes_increase: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    common_causes_decrease: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    related_kpis: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
