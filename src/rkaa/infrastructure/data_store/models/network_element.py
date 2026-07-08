"""Network element persistence model."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from rkaa.infrastructure.data_store.base import Base


class NetworkElement(Base):
    """Represents a managed network element in the inventory."""

    __tablename__ = "network_elements"
    __table_args__ = (
        CheckConstraint(
            "technology IN ('LTE', 'NR', 'NSA')",
            name="ck_network_elements_technology",
        ),
    )

    ne_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ne_name: Mapped[str] = mapped_column(String(255), nullable=False)
    vendor: Mapped[str] = mapped_column(String(100), nullable=False)
    technology: Mapped[str] = mapped_column(String(16), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    site_id: Mapped[str] = mapped_column(String(100), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
