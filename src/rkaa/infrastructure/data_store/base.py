"""SQLAlchemy declarative base for RKAA."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Root declarative base for all future ORM models."""
