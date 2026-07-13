"""API endpoints for versioned KPI knowledge entries."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from rkaa.core.exceptions import AppError
from rkaa.infrastructure.data_store.database import session_scope
from rkaa.infrastructure.data_store.models import KnowledgeEntry
from rkaa.infrastructure.data_store.repositories.knowledge_entry import (
    KnowledgeEntryRepository,
)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


class KnowledgeWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meaning_increase: str
    meaning_decrease: str
    common_causes_increase: list[str]
    common_causes_decrease: list[str]
    related_kpis: list[str]
    created_by: str
    created_at: datetime | None = None


class KnowledgeCreateRequest(KnowledgeWriteRequest):
    model_config = ConfigDict(extra="forbid")

    kpi_name: str


class KnowledgeUpdateRequest(KnowledgeWriteRequest):
    model_config = ConfigDict(extra="forbid")


class KnowledgeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    kpi_name: str
    meaning_increase: str
    meaning_decrease: str
    common_causes_increase: list[str]
    common_causes_decrease: list[str]
    related_kpis: list[str]
    created_by: str
    created_at: datetime
    version: int
    status: str


@router.post("", response_model=KnowledgeResponse)
def create_knowledge(payload: KnowledgeCreateRequest) -> KnowledgeResponse:
    with session_scope() as session:
        repository = KnowledgeEntryRepository(session)
        entry = repository.create_version(
            _build_entry(
                kpi_name=payload.kpi_name,
                payload=payload,
            )
        )
        response = _to_response(entry)

    return response


@router.put("/{entry_id}", response_model=KnowledgeResponse)
def update_knowledge(
    entry_id: int,
    payload: KnowledgeUpdateRequest,
) -> KnowledgeResponse:
    with session_scope() as session:
        repository = KnowledgeEntryRepository(session)
        current = repository.get_by_id(entry_id)
        entry = repository.create_version(
            _build_entry(
                kpi_name=current.kpi_name,
                payload=payload,
            )
        )
        response = _to_response(entry)

    return response


@router.post("/{entry_id}/approve", response_model=KnowledgeResponse)
def approve_knowledge(entry_id: int) -> KnowledgeResponse:
    with session_scope() as session:
        repository = KnowledgeEntryRepository(session)
        try:
            entry = repository.approve(entry_id)
        except ValueError as exc:
            raise AppError(str(exc), error_code="INVALID_INPUT") from exc
        response = _to_response(entry)

    return response


@router.get("/by-kpi/{kpi_name}", response_model=KnowledgeResponse)
def get_approved_knowledge(kpi_name: str) -> KnowledgeResponse:
    with session_scope() as session:
        entry = KnowledgeEntryRepository(session).get_approved(kpi_name)
        response = _to_response(entry)

    return response


def _build_entry(*, kpi_name: str, payload: KnowledgeWriteRequest) -> KnowledgeEntry:
    return KnowledgeEntry(
        kpi_name=kpi_name,
        meaning_increase=payload.meaning_increase,
        meaning_decrease=payload.meaning_decrease,
        common_causes_increase=payload.common_causes_increase,
        common_causes_decrease=payload.common_causes_decrease,
        related_kpis=payload.related_kpis,
        created_by=payload.created_by,
        created_at=payload.created_at or datetime.now(UTC),
        version=1,
        status="draft",
    )


def _to_response(entry: KnowledgeEntry) -> KnowledgeResponse:
    return KnowledgeResponse.model_validate(
        {
            "id": entry.id,
            "kpi_name": entry.kpi_name,
            "meaning_increase": entry.meaning_increase,
            "meaning_decrease": entry.meaning_decrease,
            "common_causes_increase": entry.common_causes_increase,
            "common_causes_decrease": entry.common_causes_decrease,
            "related_kpis": entry.related_kpis,
            "created_by": entry.created_by,
            "created_at": entry.created_at,
            "version": entry.version,
            "status": entry.status,
        }
    )
