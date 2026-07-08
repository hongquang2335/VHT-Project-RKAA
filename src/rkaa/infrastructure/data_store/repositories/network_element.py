"""Repository for NetworkElement persistence operations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from rkaa.core.exceptions import NotFoundError
from rkaa.infrastructure.data_store.models.network_element import NetworkElement


class NetworkElementRepository:
    """CRUD operations for network elements."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, network_element: NetworkElement) -> NetworkElement:
        self._session.add(network_element)
        self._session.flush()
        self._session.refresh(network_element)
        return network_element

    def get_by_id(self, ne_id: str) -> NetworkElement:
        network_element = self._session.get(NetworkElement, ne_id)
        if network_element is None:
            raise NotFoundError(f"Network element '{ne_id}' not found.")
        return network_element

    def list(self) -> list[NetworkElement]:
        statement = select(NetworkElement).order_by(NetworkElement.ne_id)
        return list(self._session.scalars(statement))

    def update(self, ne_id: str, **changes: object) -> NetworkElement:
        network_element = self.get_by_id(ne_id)
        for key, value in changes.items():
            setattr(network_element, key, value)
        self._session.flush()
        self._session.refresh(network_element)
        return network_element

    def delete(self, ne_id: str) -> None:
        network_element = self.get_by_id(ne_id)
        self._session.delete(network_element)
        self._session.flush()
