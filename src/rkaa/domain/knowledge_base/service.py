"""Public FR-501 Knowledge Base service API.

This service wraps the existing versioned :class:`KnowledgeStore` instead of
creating a second persistence implementation.  Reports and other application
services should depend on this API for effective (approved) knowledge lookup.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .store import KnowledgeEntry, KnowledgeStore

_MISSING_KNOWLEDGE_TEXT = "Chưa có tri thức — cần cập nhật"
_ALLOWED_APPROVER_ROLES = {"engineer", "admin"}


class KnowledgeBaseService:
    """FR-501 domain API backed by the existing versioned KnowledgeStore."""

    def __init__(self, store: KnowledgeStore) -> None:
        self.store = store

    @classmethod
    def from_path(cls, path: str | Path) -> "KnowledgeBaseService":
        return cls(KnowledgeStore(path))

    def get(self, kpi_name: str, *, approved_only: bool = True) -> dict[str, Any] | None:
        """Return the latest effective version for one KPI.

        BR-06 requires reports to consume approved knowledge only, therefore
        ``approved_only`` defaults to ``True``.
        """

        return self.store.latest(str(kpi_name), approved_only=approved_only)

    def update(self, entry: KnowledgeEntry) -> dict[str, Any]:
        """Append a new version; prior versions remain available in history."""

        return self.store.upsert(entry)

    def history(self, kpi_name: str) -> list[dict[str, Any]]:
        return self.store.history(str(kpi_name))

    def import_file(
        self,
        path: str | Path,
        *,
        allow_approved: bool = False,
    ) -> list[dict[str, Any]]:
        """Import JSON/CSV as pending by default; trusted seeds may opt in."""

        return self.store.import_file(path, allow_approved=allow_approved)

    def search(
        self,
        query: str = "",
        *,
        approved_only: bool = True,
    ) -> list[dict[str, Any]]:
        """Search KPI knowledge by name/display name/description/related KPI."""

        needle = str(query).strip().casefold()
        rows = self.store.list_latest(approved_only=approved_only)
        if not needle:
            return rows

        matches: list[dict[str, Any]] = []
        for record in rows:
            haystack = " ".join(
                [
                    str(record.get("kpi_name", "")),
                    str(record.get("display_name", "")),
                    str(record.get("description", "")),
                    " ".join(str(item) for item in record.get("related_kpis") or []),
                ]
            ).casefold()
            if needle in haystack:
                matches.append(record)
        return matches

    def approve(
        self,
        kpi_name: str,
        version: int,
        *,
        approved_by: str,
        approver_role: str,
    ) -> dict[str, Any]:
        """Approve one version while enforcing BR-06 (Engineer or Admin)."""

        role = str(approver_role).strip().casefold()
        if role not in _ALLOWED_APPROVER_ROLES:
            raise PermissionError("BR-06 yêu cầu vai trò Engineer hoặc Admin để phê duyệt Knowledge Base")
        if not str(approved_by).strip():
            raise ValueError("approved_by không được rỗng")
        return self.store.approve(
            str(kpi_name),
            int(version),
            approved_by=str(approved_by).strip(),
            approver_role=role,
        )


    def list_patterns(
        self,
        *,
        kpi_name: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return FR-503 pattern suggestions stored in the Knowledge Base."""

        return self.store.list_patterns(kpi_name=kpi_name, status=status)

    def approved_patterns_for_kpi(self, kpi_name: str) -> list[dict[str, Any]]:
        return self.store.list_patterns(kpi_name=str(kpi_name), status="APPROVED")

    def save_pattern_suggestion(self, record: dict[str, Any]) -> dict[str, Any]:
        """Persist a FR-503 suggestion without bypassing the KB authority."""

        payload = deepcopy(record)
        payload.setdefault("status", "PENDING")
        return self.store.upsert_pattern(payload)

    def review_pattern(
        self,
        pattern_id: str,
        *,
        action: str,
        reviewed_by: str,
        reviewer_role: str,
        edited_summary: str | None = None,
    ) -> dict[str, Any]:
        """Approve/reject/edit a FR-503 suggestion with BR-06 role enforcement."""

        role = str(reviewer_role).strip().casefold()
        if role not in _ALLOWED_APPROVER_ROLES:
            raise PermissionError("BR-06 yêu cầu vai trò Engineer hoặc Admin để duyệt pattern")
        if not str(reviewed_by).strip():
            raise ValueError("reviewed_by không được rỗng")
        normalized_action = str(action).strip().upper()
        if normalized_action not in {"APPROVE", "REJECT", "EDIT"}:
            raise ValueError("action phải là APPROVE, REJECT hoặc EDIT")

        current = self.store.get_pattern(str(pattern_id))
        if current is None:
            raise KeyError(f"Không tìm thấy pattern {pattern_id}")
        if edited_summary is not None:
            summary = str(edited_summary).strip()
            if not summary:
                raise ValueError("edited_summary không được rỗng")
            current["summary"] = summary

        if normalized_action == "APPROVE":
            current["status"] = "APPROVED"
        elif normalized_action == "REJECT":
            current["status"] = "REJECTED"
        else:
            current["status"] = "PENDING"

        current["reviewed_by"] = str(reviewed_by).strip()
        current["reviewer_role"] = role
        current["review_action"] = normalized_action
        return self.store.upsert_pattern(current)

    def explain_change(
        self,
        kpi_name: str,
        *,
        direction: str,
    ) -> dict[str, Any]:
        """Resolve FR-502 explanation for an increase/decrease of one KPI.

        The lookup is exact by KPI name.  No semantic aliasing is performed,
        because the SRS does not define aliases between vendor KPI names.
        """

        normalized_direction = str(direction).strip().upper()
        if normalized_direction not in {"INCREASE", "DECREASE", "NO_CHANGE"}:
            raise ValueError("direction phải là INCREASE, DECREASE hoặc NO_CHANGE")

        record = self.get(str(kpi_name), approved_only=True)
        if record is None:
            return {
                "kpi_name": str(kpi_name),
                "knowledge_status": "MISSING",
                "knowledge_available": False,
                "knowledge_version": None,
                "knowledge_meaning": _MISSING_KNOWLEDGE_TEXT,
                "knowledge_source": "",
            }

        if normalized_direction == "INCREASE":
            meaning = str(record.get("meaning_increase", "")).strip()
        elif normalized_direction == "DECREASE":
            meaning = str(record.get("meaning_decrease", "")).strip()
        else:
            meaning = str(record.get("description", "")).strip()

        if not meaning:
            meaning = _MISSING_KNOWLEDGE_TEXT
            status = "MISSING_MEANING"
        else:
            status = "FOUND"

        return {
            "kpi_name": str(kpi_name),
            "knowledge_status": status,
            "knowledge_available": status == "FOUND",
            "knowledge_version": int(record.get("version", 0)) or None,
            "knowledge_meaning": meaning,
            "knowledge_source": str(record.get("source", "")),
        }


__all__ = ["KnowledgeBaseService", "_MISSING_KNOWLEDGE_TEXT"]
