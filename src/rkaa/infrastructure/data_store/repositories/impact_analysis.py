"""Repository for ImpactAnalysis and KPIDelta persistence operations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from rkaa.core.exceptions import NotFoundError
from rkaa.infrastructure.data_store.models.impact_analysis import ImpactAnalysis, KPIDelta


class ImpactAnalysisRepository:
    """CRUD-style persistence helpers for impact analysis results."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, analysis: ImpactAnalysis) -> ImpactAnalysis:
        self._session.add(analysis)
        self._session.flush()
        self._session.refresh(analysis)
        return analysis

    def bulk_create_deltas(self, deltas: list[KPIDelta]) -> list[KPIDelta]:
        self._session.add_all(deltas)
        self._session.flush()
        for delta in deltas:
            self._session.refresh(delta)
        return deltas

    def get_by_id(self, analysis_id: int) -> ImpactAnalysis:
        analysis = self._session.get(ImpactAnalysis, analysis_id)
        if analysis is None:
            raise NotFoundError(f"Impact analysis '{analysis_id}' not found.")
        return analysis

    def list_by_impact_event_id(self, impact_event_id: int) -> list[ImpactAnalysis]:
        statement = (
            select(ImpactAnalysis)
            .where(ImpactAnalysis.impact_event_id == impact_event_id)
            .order_by(ImpactAnalysis.analyzed_at.desc(), ImpactAnalysis.id.desc())
        )
        return list(self._session.scalars(statement))

    def list_deltas_by_analysis_id(self, analysis_id: int) -> list[KPIDelta]:
        statement = (
            select(KPIDelta)
            .where(KPIDelta.analysis_id == analysis_id)
            .order_by(KPIDelta.kpi_name, KPIDelta.id)
        )
        return list(self._session.scalars(statement))
