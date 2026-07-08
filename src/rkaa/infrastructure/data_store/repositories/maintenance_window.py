"""Repository for MaintenanceWindow persistence operations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from rkaa.core.exceptions import NotFoundError
from rkaa.infrastructure.data_store.models.maintenance_window import MaintenanceWindow


class MaintenanceWindowRepository:
    """CRUD operations for maintenance windows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, maintenance_window: MaintenanceWindow) -> MaintenanceWindow:
        self._session.add(maintenance_window)
        self._session.flush()
        self._session.refresh(maintenance_window)
        return maintenance_window

    def get_by_id(self, window_id: int) -> MaintenanceWindow:
        maintenance_window = self._session.get(MaintenanceWindow, window_id)
        if maintenance_window is None:
            raise NotFoundError(f"Maintenance window '{window_id}' not found.")
        return maintenance_window

    def list(self) -> list[MaintenanceWindow]:
        statement = select(MaintenanceWindow).order_by(
            MaintenanceWindow.start_time,
            MaintenanceWindow.id,
        )
        return list(self._session.scalars(statement))

    def update(self, window_id: int, **changes: object) -> MaintenanceWindow:
        maintenance_window = self.get_by_id(window_id)
        for key, value in changes.items():
            setattr(maintenance_window, key, value)
        self._session.flush()
        self._session.refresh(maintenance_window)
        return maintenance_window

    def delete(self, window_id: int) -> None:
        maintenance_window = self.get_by_id(window_id)
        self._session.delete(maintenance_window)
        self._session.flush()
