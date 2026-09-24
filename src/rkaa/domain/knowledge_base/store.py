"""FR-501 file-backed Knowledge Base with version history and runtime observations."""

from __future__ import annotations

import csv
import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


@dataclass(slots=True)
class KnowledgeEntry:
    kpi_name: str
    display_name: str = ""
    unit: str = ""
    description: str = ""
    direction_preference: str = "informational"
    meaning_increase: str = ""
    meaning_decrease: str = ""
    common_causes_increase: list[str] = field(default_factory=list)
    common_causes_decrease: list[str] = field(default_factory=list)
    related_kpis: list[str] = field(default_factory=list)
    reference_thresholds: dict[str, Any] = field(default_factory=dict)
    operational_notes: list[dict[str, Any]] = field(default_factory=list)
    source: str = "manual"
    approved: bool = False
    created_by: str = "system"

    def as_record(self) -> dict[str, Any]:
        return {
            "kpi_name": self.kpi_name,
            "display_name": self.display_name or self.kpi_name,
            "unit": self.unit,
            "description": self.description,
            "direction_preference": self.direction_preference,
            "meaning_increase": self.meaning_increase,
            "meaning_decrease": self.meaning_decrease,
            "common_causes_increase": list(self.common_causes_increase),
            "common_causes_decrease": list(self.common_causes_decrease),
            "related_kpis": list(self.related_kpis),
            "reference_thresholds": dict(self.reference_thresholds),
            "operational_notes": deepcopy(self.operational_notes),
            "source": self.source,
            "approved": bool(self.approved),
            "created_by": self.created_by,
        }


class KnowledgeStore:
    """Simple JSON store used by FR-501 until a database backend is introduced.

    The schema keeps every version of each KPI entry. Reports should use the
    latest approved version, matching BR-06, while pending runtime observations
    remain visible in history for engineer review.
    """

    SCHEMA_VERSION = 2

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self._data = self._load()
        else:
            self._data = {"schema_version": self.SCHEMA_VERSION, "records": {}, "patterns": {}}

    def _load(self) -> dict[str, Any]:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or "records" not in raw:
            raise ValueError("Knowledge store không đúng schema")
        # Backward-compatible schema evolution for FR-503. Existing FR-501
        # stores remain valid; pattern suggestions live in the same Knowledge
        # Store rather than creating a second persistence authority.
        raw.setdefault("patterns", {})
        raw["schema_version"] = max(int(raw.get("schema_version", 1)), self.SCHEMA_VERSION)
        return raw

    def save(self) -> None:
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def upsert(self, entry: KnowledgeEntry) -> dict[str, Any]:
        name = str(entry.kpi_name).strip()
        if not name:
            raise ValueError("kpi_name không được rỗng")
        versions = self._data["records"].setdefault(name, [])
        record = entry.as_record()
        record["kpi_name"] = name
        record["version"] = (max((int(v.get("version", 0)) for v in versions), default=0) + 1)
        record["created_at"] = datetime.now(timezone.utc).isoformat()
        versions.append(record)
        self.save()
        return deepcopy(record)

    def history(self, kpi_name: str) -> list[dict[str, Any]]:
        return deepcopy(self._data["records"].get(kpi_name, []))

    def latest(self, kpi_name: str, *, approved_only: bool = True) -> dict[str, Any] | None:
        versions = self._data["records"].get(kpi_name, [])
        if approved_only:
            versions = [v for v in versions if bool(v.get("approved"))]
        if not versions:
            return None
        return deepcopy(max(versions, key=lambda item: int(item.get("version", 0))))

    def latest_any(self, kpi_name: str) -> dict[str, Any] | None:
        return self.latest(kpi_name, approved_only=False)

    def approve(
        self,
        kpi_name: str,
        version: int,
        *,
        approved_by: str | None = None,
        approver_role: str | None = None,
    ) -> dict[str, Any]:
        versions = self._data["records"].get(kpi_name, [])
        for record in versions:
            if int(record.get("version", 0)) == int(version):
                record["approved"] = True
                record["approved_at"] = datetime.now(timezone.utc).isoformat()
                if approved_by is not None:
                    record["approved_by"] = str(approved_by)
                if approver_role is not None:
                    record["approver_role"] = str(approver_role)
                self.save()
                return deepcopy(record)
        raise KeyError(f"Không tìm thấy {kpi_name} version={version}")

    def list_latest(self, *, approved_only: bool = True) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for kpi_name in sorted(self._data["records"]):
            record = self.latest(kpi_name, approved_only=approved_only)
            if record is not None:
                rows.append(record)
        return rows


    def upsert_pattern(self, record: dict[str, Any]) -> dict[str, Any]:
        """Create or replace one FR-503 pattern suggestion in the same KB store."""

        pattern_id = str(record.get("pattern_id", "")).strip()
        if not pattern_id:
            raise ValueError("pattern_id không được rỗng")
        payload = deepcopy(record)
        payload["pattern_id"] = pattern_id
        payload.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._data.setdefault("patterns", {})[pattern_id] = payload
        self.save()
        return deepcopy(payload)

    def get_pattern(self, pattern_id: str) -> dict[str, Any] | None:
        record = self._data.setdefault("patterns", {}).get(str(pattern_id))
        return deepcopy(record) if record is not None else None

    def list_patterns(
        self,
        *,
        kpi_name: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = [deepcopy(item) for item in self._data.setdefault("patterns", {}).values()]
        if kpi_name is not None:
            rows = [row for row in rows if str(row.get("kpi_name")) == str(kpi_name)]
        if status is not None:
            wanted = str(status).strip().upper()
            rows = [row for row in rows if str(row.get("status", "")).upper() == wanted]
        return sorted(rows, key=lambda row: (str(row.get("kpi_name", "")), str(row.get("pattern_id", ""))))

    def import_records(
        self,
        records: Iterable[dict[str, Any]],
        *,
        allow_approved: bool = False,
    ) -> list[dict[str, Any]]:
        imported: list[dict[str, Any]] = []
        for raw in records:
            entry = KnowledgeEntry(
                kpi_name=str(raw.get("kpi_name", "")).strip(),
                display_name=str(raw.get("display_name", "")),
                unit=str(raw.get("unit", "")),
                description=str(raw.get("description", "")),
                direction_preference=str(raw.get("direction_preference", "informational")),
                meaning_increase=str(raw.get("meaning_increase", "")),
                meaning_decrease=str(raw.get("meaning_decrease", "")),
                common_causes_increase=_as_list(raw.get("common_causes_increase")),
                common_causes_decrease=_as_list(raw.get("common_causes_decrease")),
                related_kpis=_as_list(raw.get("related_kpis")),
                reference_thresholds=_as_dict(raw.get("reference_thresholds")),
                operational_notes=_as_note_list(raw.get("operational_notes")),
                source=str(raw.get("source", "import")),
                approved=_as_bool(raw.get("approved", False)) if allow_approved else False,
                created_by=str(raw.get("created_by", "import")),
            )
            imported.append(self.upsert(entry))
        return imported

    def import_file(
        self,
        path: str | Path,
        *,
        allow_approved: bool = False,
    ) -> list[dict[str, Any]]:
        source = Path(path)
        suffix = source.suffix.lower()
        if suffix == ".json":
            payload = json.loads(source.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                records = payload.get("records", payload.get("entries", []))
            else:
                records = payload
            if not isinstance(records, list):
                raise ValueError("JSON knowledge import phải chứa list records")
            return self.import_records(records, allow_approved=allow_approved)
        if suffix == ".csv":
            with source.open("r", encoding="utf-8-sig", newline="") as handle:
                return self.import_records(
                    csv.DictReader(handle), allow_approved=allow_approved
                )
        raise ValueError("FR-501 chỉ hỗ trợ import JSON hoặc CSV")


def _as_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except json.JSONDecodeError:
                pass
        return [item.strip() for item in text.split(";") if item.strip()]
    return [str(value)]


def _as_note_list(value: Any) -> list[dict[str, Any]]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [dict(item) if isinstance(item, dict) else {"note": str(item)} for item in value]
    if isinstance(value, str) and value.strip().startswith("["):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return _as_note_list(parsed)
        except json.JSONDecodeError:
            pass
    return [{"note": str(value)}]


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}
