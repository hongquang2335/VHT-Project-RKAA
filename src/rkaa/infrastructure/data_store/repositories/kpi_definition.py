"""Repository for KPIDefinition persistence operations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from rkaa.core.exceptions import NotFoundError
from rkaa.infrastructure.data_store.models.kpi_definition import KPIDefinition


class KPIDefinitionRepository:
    """CRUD operations for KPI definitions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, kpi_definition: KPIDefinition) -> KPIDefinition:
        self._session.add(kpi_definition)
        self._session.flush()
        self._session.refresh(kpi_definition)
        return kpi_definition

    def get_by_name(self, kpi_name: str) -> KPIDefinition:
        kpi_definition = self._session.get(KPIDefinition, kpi_name)
        if kpi_definition is None:
            raise NotFoundError(f"KPI definition '{kpi_name}' not found.")
        return kpi_definition

    def list(self) -> list[KPIDefinition]:
        statement = select(KPIDefinition).order_by(KPIDefinition.kpi_name)
        return list(self._session.scalars(statement))

    def update(self, kpi_name: str, **changes: object) -> KPIDefinition:
        kpi_definition = self.get_by_name(kpi_name)
        for key, value in changes.items():
            setattr(kpi_definition, key, value)
        self._session.flush()
        self._session.refresh(kpi_definition)
        return kpi_definition

    def delete(self, kpi_name: str) -> None:
        kpi_definition = self.get_by_name(kpi_name)
        self._session.delete(kpi_definition)
        self._session.flush()
