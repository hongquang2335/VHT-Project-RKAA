"""Repository for KnowledgeEntry persistence operations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from rkaa.core.exceptions import NotFoundError
from rkaa.infrastructure.data_store.models.knowledge_entry import KnowledgeEntry


class KnowledgeEntryRepository:
    """Persistence operations for versioned KPI knowledge entries."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_version(self, entry: KnowledgeEntry) -> KnowledgeEntry:
        entry.version = self._next_version(entry.kpi_name)
        entry.status = "draft"
        self._session.add(entry)
        self._session.flush()
        self._session.refresh(entry)
        return entry

    def get_by_id(self, entry_id: int) -> KnowledgeEntry:
        return self._get_by_id(entry_id)

    def approve(self, entry_id: int) -> KnowledgeEntry:
        entry = self._get_by_id(entry_id)
        if entry.status == "deprecated":
            raise ValueError("Deprecated knowledge entries cannot be approved.")

        approved_entries = self._session.scalars(
            select(KnowledgeEntry).where(
                KnowledgeEntry.kpi_name == entry.kpi_name,
                KnowledgeEntry.status == "approved",
                KnowledgeEntry.id != entry.id,
            )
        ).all()
        for approved_entry in approved_entries:
            approved_entry.status = "deprecated"

        entry.status = "approved"
        self._session.flush()
        self._session.refresh(entry)
        return entry

    def deprecate(self, entry_id: int) -> KnowledgeEntry:
        entry = self._get_by_id(entry_id)
        entry.status = "deprecated"
        self._session.flush()
        self._session.refresh(entry)
        return entry

    def get_latest(self, kpi_name: str) -> KnowledgeEntry:
        statement = (
            select(KnowledgeEntry)
            .where(KnowledgeEntry.kpi_name == kpi_name)
            .order_by(KnowledgeEntry.version.desc(), KnowledgeEntry.id.desc())
        )
        entry = self._session.scalars(statement).first()
        if entry is None:
            raise NotFoundError(f"Knowledge entry for KPI '{kpi_name}' not found.")
        return entry

    def get_approved(self, kpi_name: str) -> KnowledgeEntry:
        statement = (
            select(KnowledgeEntry)
            .where(
                KnowledgeEntry.kpi_name == kpi_name,
                KnowledgeEntry.status == "approved",
            )
            .order_by(KnowledgeEntry.version.desc(), KnowledgeEntry.id.desc())
        )
        entry = self._session.scalars(statement).first()
        if entry is None:
            raise NotFoundError(f"Approved knowledge entry for KPI '{kpi_name}' not found.")
        return entry

    def list_versions(self, kpi_name: str) -> list[KnowledgeEntry]:
        statement = (
            select(KnowledgeEntry)
            .where(KnowledgeEntry.kpi_name == kpi_name)
            .order_by(KnowledgeEntry.version, KnowledgeEntry.id)
        )
        return list(self._session.scalars(statement))

    def search(self, query: str) -> list[KnowledgeEntry]:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return []

        statement = select(KnowledgeEntry).order_by(
            KnowledgeEntry.kpi_name,
            KnowledgeEntry.version.desc(),
            KnowledgeEntry.id.desc(),
        )
        results = list(self._session.scalars(statement))
        return [
            entry
            for entry in results
            if normalized_query in _search_document(entry)
        ]

    def _next_version(self, kpi_name: str) -> int:
        statement = select(KnowledgeEntry.version).where(KnowledgeEntry.kpi_name == kpi_name)
        latest_version = self._session.scalars(statement).all()
        if not latest_version:
            return 1
        return max(latest_version) + 1

    def _get_by_id(self, entry_id: int) -> KnowledgeEntry:
        entry = self._session.get(KnowledgeEntry, entry_id)
        if entry is None:
            raise NotFoundError(f"Knowledge entry '{entry_id}' not found.")
        return entry


def _search_document(entry: KnowledgeEntry) -> str:
    fields: list[str] = [
        entry.kpi_name,
        entry.meaning_increase,
        entry.meaning_decrease,
        entry.created_by,
        entry.status,
        *entry.common_causes_increase,
        *entry.common_causes_decrease,
        *entry.related_kpis,
    ]
    return " ".join(field.lower() for field in fields)
