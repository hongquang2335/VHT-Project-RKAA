"""API endpoints for impact event management."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, ConfigDict

from rkaa.domain.impact_service import (
    create_impact_event,
    update_impact_event,
    update_impact_event_status,
)
from rkaa.infrastructure.data_store.database import session_scope
from rkaa.infrastructure.data_store.repositories.impact_event import ImpactEventRepository
from rkaa.infrastructure.data_store.repositories.network_element import (
    NetworkElementRepository,
)

router = APIRouter(prefix="/api/v1/impacts", tags=["impacts"])


class ImpactCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ne_id: str
    t1: datetime
    t2: datetime | None = None
    impact_type: str
    description: str | None = None
    operator: str | None = None
    source: str
    status: str = "draft"


class ImpactUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ne_id: str | None = None
    t1: datetime | None = None
    t2: datetime | None = None
    impact_type: str | None = None
    description: str | None = None
    operator: str | None = None
    source: str | None = None
    status: str | None = None


class ImpactResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    ne_id: str
    t1: datetime
    t2: datetime | None
    impact_type: str
    description: str | None
    operator: str | None
    source: str
    status: str


@router.post("", response_model=ImpactResponse)
def create_impact(payload: ImpactCreateRequest) -> ImpactResponse:
    with session_scope() as session:
        impact = create_impact_event(
            network_elements=NetworkElementRepository(session),
            impacts=ImpactEventRepository(session),
            ne_id=payload.ne_id,
            t1=payload.t1,
            t2=payload.t2,
            impact_type=payload.impact_type,
            description=payload.description,
            operator=payload.operator,
            source=payload.source,
            status=payload.status,
        )
        response = _to_response(impact)

    return response


@router.get("/{impact_id}", response_model=ImpactResponse)
def get_impact(impact_id: int) -> ImpactResponse:
    with session_scope() as session:
        impact = ImpactEventRepository(session).get_by_id(impact_id)
        response = _to_response(impact)

    return response


@router.put("/{impact_id}", response_model=ImpactResponse)
def update_impact(impact_id: int, payload: ImpactUpdateRequest) -> ImpactResponse:
    with session_scope() as session:
        network_elements = NetworkElementRepository(session)
        impacts = ImpactEventRepository(session)

        if any(
            field in payload.model_fields_set
            for field in ("ne_id", "t1", "t2", "impact_type", "description", "operator", "source")
        ):
            update_impact_event(
                network_elements=network_elements,
                impacts=impacts,
                event_id=impact_id,
                ne_id=payload.ne_id,
                t1=payload.t1,
                t2=payload.t2 if "t2" in payload.model_fields_set else None,
                update_t2="t2" in payload.model_fields_set,
                impact_type=payload.impact_type,
                description=payload.description,
                operator=payload.operator,
                source=payload.source,
            )

        if payload.status is not None:
            impact = update_impact_event_status(
                impacts=impacts,
                event_id=impact_id,
                status=payload.status,
            )
        else:
            impact = impacts.get_by_id(impact_id)

        response = _to_response(impact)

    return response


@router.delete("/{impact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_impact(impact_id: int) -> Response:
    with session_scope() as session:
        ImpactEventRepository(session).delete(impact_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _to_response(impact: object) -> ImpactResponse:
    return ImpactResponse.model_validate(
        {
            "id": getattr(impact, "id"),
            "ne_id": getattr(impact, "ne_id"),
            "t1": getattr(impact, "t1"),
            "t2": getattr(impact, "t2"),
            "impact_type": getattr(impact, "impact_type"),
            "description": getattr(impact, "description"),
            "operator": getattr(impact, "operator"),
            "source": getattr(impact, "source"),
            "status": getattr(impact, "status"),
        }
    )
