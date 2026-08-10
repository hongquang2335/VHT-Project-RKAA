"""Hợp đồng lưu trữ mà tầng nghiệp vụ FR-103/FR-202 sử dụng."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from rkaa.domain.impact_manager.models import EventCategory, ImpactEvent, ImpactStatus


@runtime_checkable
class ImpactRepository(Protocol):
    """Giao diện tách tầng nghiệp vụ khỏi công nghệ lưu trữ cụ thể."""

    def create(self, event: ImpactEvent) -> ImpactEvent:
        ...

    def get_by_id(
        self,
        impact_id: str,
        *,
        include_deleted: bool = False,
    ) -> ImpactEvent | None:
        ...

    def list_events(
        self,
        *,
        ne_id: str | None = None,
        cell_id: str | None = None,
        status: ImpactStatus | None = None,
        event_category: EventCategory | None = None,
        exclude_from_baseline: bool | None = None,
        include_deleted: bool = False,
    ) -> list[ImpactEvent]:
        ...

    def update(self, event: ImpactEvent) -> ImpactEvent:
        ...

    def soft_delete(
        self,
        impact_id: str,
        deleted_at_utc: datetime,
    ) -> bool:
        ...
