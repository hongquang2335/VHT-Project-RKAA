"""Repository for ImpactEvent persistence operations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from rkaa.core.exceptions import NotFoundError
from rkaa.infrastructure.data_store.models.impact_event import ImpactEvent


class ImpactEventRepository:
    """CRUD operations for impact events."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, impact_event: ImpactEvent) -> ImpactEvent:
        self._session.add(impact_event)
        self._session.flush()
        self._session.refresh(impact_event)
        return impact_event

    def get_by_id(self, event_id: int) -> ImpactEvent:
        impact_event = self._session.get(ImpactEvent, event_id)
        if impact_event is None:
            raise NotFoundError(f"Impact event '{event_id}' not found.")
        return impact_event

    def list(self) -> list[ImpactEvent]:
        statement = select(ImpactEvent).order_by(ImpactEvent.t1, ImpactEvent.id)
        return list(self._session.scalars(statement))

    def update(self, event_id: int, **changes: object) -> ImpactEvent:
        impact_event = self.get_by_id(event_id)
        for key, value in changes.items():
            setattr(impact_event, key, value)
        self._session.flush()
        self._session.refresh(impact_event)
        return impact_event

    def delete(self, event_id: int) -> None:
        impact_event = self.get_by_id(event_id)
        self._session.delete(impact_event)
        self._session.flush()
