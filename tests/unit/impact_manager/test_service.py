from dataclasses import replace
from datetime import datetime, timezone
from time import perf_counter
from uuid import UUID

import pytest

from rkaa.domain.impact_manager.models import (
    CreateImpactRequest,
    ImpactEvent,
    ImpactStatus,
    UpdateImpactRequest,
)
from rkaa.domain.impact_manager.service import ImpactManagerService


class FakeImpactRepository:
    def __init__(self) -> None:
        self.events: dict[str, ImpactEvent] = {}

    def create(self, event: ImpactEvent) -> ImpactEvent:
        if event.impact_id in self.events:
            raise ValueError("duplicate")
        self.events[event.impact_id] = event
        return event

    def get_by_id(
        self,
        impact_id: str,
        *,
        include_deleted: bool = False,
    ) -> ImpactEvent | None:
        event = self.events.get(impact_id)
        if event is None:
            return None
        if not include_deleted and event.status is ImpactStatus.DELETED:
            return None
        return event

    def list_events(
        self,
        *,
        ne_id: str | None = None,
        cell_id: str | None = None,
        status: ImpactStatus | None = None,
        include_deleted: bool = False,
    ) -> list[ImpactEvent]:
        events = list(self.events.values())
        if not include_deleted:
            events = [item for item in events if item.status is not ImpactStatus.DELETED]
        if ne_id is not None:
            events = [item for item in events if item.ne_id == ne_id]
        if cell_id is not None:
            events = [item for item in events if item.cell_id == cell_id]
        if status is not None:
            events = [item for item in events if item.status is status]
        return sorted(events, key=lambda item: item.t1_utc, reverse=True)

    def update(self, event: ImpactEvent) -> ImpactEvent:
        if event.impact_id not in self.events:
            raise LookupError(event.impact_id)
        self.events[event.impact_id] = event
        return event

    def soft_delete(self, impact_id: str, deleted_at_utc: datetime) -> bool:
        event = self.events.get(impact_id)
        if event is None or event.status is ImpactStatus.DELETED:
            return False
        self.events[impact_id] = replace(
            event,
            status=ImpactStatus.DELETED,
            deleted_at_utc=deleted_at_utc,
            updated_at_utc=deleted_at_utc,
        )
        return True


@pytest.fixture
def service() -> ImpactManagerService:
    return ImpactManagerService(
        FakeImpactRepository(),
        allowed_impact_types={"NE_RESTART", "CONFIGURATION_CHANGE"},
        input_timezone="Asia/Ho_Chi_Minh",
    )


def create_request(t2: str = "ongoing") -> CreateImpactRequest:
    return CreateImpactRequest(
        ne_id="gHM00001",
        cell_id="gHM00001_30",
        t1="2026-07-15 16:50:00",
        t2=t2,
        impact_type="NE_RESTART",
        description="Khởi động lại NE",
        operator="engineer_a",
    )


def test_create_ongoing_event_has_uuid(service: ImpactManagerService) -> None:
    event = service.create_impact(create_request())

    UUID(event.impact_id)
    assert event.status is ImpactStatus.ONGOING
    assert event.t2_utc is None
    assert event.t1_utc.isoformat() == "2026-07-15T09:50:00+00:00"


def test_create_closed_event(service: ImpactManagerService) -> None:
    event = service.create_impact(create_request("2026-07-15 17:20:00"))

    assert event.status is ImpactStatus.CLOSED
    assert event.t2_utc is not None


def test_two_events_have_different_uuid(service: ImpactManagerService) -> None:
    first = service.create_impact(create_request())
    second = service.create_impact(create_request())
    assert first.impact_id != second.impact_id


def test_close_ongoing_event(service: ImpactManagerService) -> None:
    event = service.create_impact(create_request())
    closed = service.close_impact(event.impact_id, "2026-07-15 17:20:00")

    assert closed.status is ImpactStatus.CLOSED
    assert closed.t2_utc is not None


def test_cannot_close_closed_event(service: ImpactManagerService) -> None:
    event = service.create_impact(create_request("2026-07-15 17:20:00"))
    with pytest.raises(ValueError, match="ONGOING"):
        service.close_impact(event.impact_id, "2026-07-15 18:00:00")


def test_update_description_and_clear_cell(service: ImpactManagerService) -> None:
    event = service.create_impact(create_request())
    updated = service.update_impact(
        event.impact_id,
        UpdateImpactRequest(
            description="Mô tả đã sửa",
            clear_cell=True,
        ),
    )

    assert updated.description == "Mô tả đã sửa"
    assert updated.cell_id is None


def test_update_can_change_closed_event_to_ongoing(service: ImpactManagerService) -> None:
    event = service.create_impact(create_request("2026-07-15 17:20:00"))
    updated = service.update_impact(
        event.impact_id,
        UpdateImpactRequest(t2="ongoing"),
    )
    assert updated.status is ImpactStatus.ONGOING
    assert updated.t2_utc is None


def test_delete_is_soft_delete(service: ImpactManagerService) -> None:
    event = service.create_impact(create_request())
    service.delete_impact(event.impact_id)

    with pytest.raises(LookupError):
        service.get_impact(event.impact_id)

    deleted = service.get_impact(event.impact_id, include_deleted=True)
    assert deleted.status is ImpactStatus.DELETED
    assert deleted.deleted_at_utc is not None


def test_list_filters_by_status(service: ImpactManagerService) -> None:
    service.create_impact(create_request())
    service.create_impact(create_request("2026-07-15 17:20:00"))

    ongoing = service.list_impacts(status="ONGOING")
    assert len(ongoing) == 1
    assert ongoing[0].status is ImpactStatus.ONGOING


def test_create_completes_within_two_seconds(service: ImpactManagerService) -> None:
    started = perf_counter()
    service.create_impact(create_request())
    elapsed = perf_counter() - started
    assert elapsed <= 2.0


def test_created_timestamps_are_utc(service: ImpactManagerService) -> None:
    event = service.create_impact(create_request())
    assert event.created_at_utc.tzinfo is timezone.utc
    assert event.updated_at_utc.tzinfo is timezone.utc
