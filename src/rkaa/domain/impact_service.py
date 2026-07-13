"""Service for managing impact event lifecycle rules."""

from __future__ import annotations

from datetime import datetime

from rkaa.core.exceptions import AppError
from rkaa.infrastructure.data_store.models.impact_event import ImpactEvent
from rkaa.infrastructure.data_store.repositories.impact_event import ImpactEventRepository
from rkaa.infrastructure.data_store.repositories.network_element import (
    NetworkElementRepository,
)

_UNSET = object()

ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"confirmed", "cancelled"},
    "confirmed": {"analyzed", "cancelled"},
    "analyzed": set(),
    "cancelled": set(),
}


def create_impact_event(
    *,
    network_elements: NetworkElementRepository,
    impacts: ImpactEventRepository,
    ne_id: str,
    t1: datetime,
    t2: datetime | None,
    impact_type: str,
    description: str | None,
    operator: str | None,
    source: str,
    status: str = "draft",
) -> ImpactEvent:
    """Create a new impact event after validating lifecycle prerequisites."""

    network_elements.get_by_id(ne_id)
    _validate_status_value(status)

    return impacts.create(
        ImpactEvent(
            ne_id=ne_id,
            t1=t1,
            t2=t2,
            impact_type=impact_type,
            description=description,
            operator=operator,
            source=source,
            status=status,
        )
    )


def update_impact_event_status(
    *,
    impacts: ImpactEventRepository,
    event_id: int,
    status: str,
) -> ImpactEvent:
    """Update impact status while enforcing allowed lifecycle transitions."""

    impact_event = impacts.get_by_id(event_id)
    _validate_status_transition(current_status=impact_event.status, next_status=status)
    return impacts.update(event_id, status=status)


def update_impact_event(
    *,
    network_elements: NetworkElementRepository,
    impacts: ImpactEventRepository,
    event_id: int,
    ne_id: str | None = None,
    t1: datetime | None = None,
    t2: datetime | None | object = _UNSET,
    update_t2: bool = False,
    impact_type: str | None = None,
    description: str | None = None,
    operator: str | None = None,
    source: str | None = None,
) -> ImpactEvent:
    """Update mutable impact fields while ensuring referenced NE exists."""

    if ne_id is not None:
        network_elements.get_by_id(ne_id)

    changes = {
        key: value
        for key, value in {
            "ne_id": ne_id,
            "t1": t1,
            "t2": t2,
            "impact_type": impact_type,
            "description": description,
            "operator": operator,
            "source": source,
        }.items()
        if value is not None and value is not _UNSET
    }
    if update_t2 and t2 is None:
        changes["t2"] = None
    return impacts.update(event_id, **changes)


def _validate_status_value(status: str) -> None:
    if status not in ALLOWED_STATUS_TRANSITIONS:
        raise AppError(
            f"Invalid impact status '{status}'.",
            error_code="INVALID_INPUT",
            details={"status": status},
        )


def _validate_status_transition(*, current_status: str, next_status: str) -> None:
    _validate_status_value(next_status)
    if next_status == current_status:
        return

    allowed_next = ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
    if next_status not in allowed_next:
        raise AppError(
            f"Invalid impact status transition from '{current_status}' to '{next_status}'.",
            error_code="INVALID_INPUT",
            details={
                "current_status": current_status,
                "next_status": next_status,
            },
        )
