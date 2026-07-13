from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rkaa.core.config import load_settings
from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.database import get_engine, initialize_database, session_scope
from rkaa.infrastructure.data_store.models import KPIDefinition
from rkaa.infrastructure.data_store.repositories.knowledge_entry import (
    KnowledgeEntryRepository,
)
from rkaa.main import app


def _config_content(database_url: str) -> str:
    return f"""
app:
  name: "RKAA Test"
  timezone: "UTC"
  granularity_minutes: 15
  baseline_min_clean_days: 14
  day_periods:
    busy:
      start: "07:00"
      end: "10:00"
    transition:
      start: "10:00"
      end: "17:00"
    off_peak:
      start: "17:00"
      end: "07:00"
database:
  url: "{database_url}"
logging:
  level: "INFO"
""".strip()


def _seed_kpi_definition(kpi_name: str = "erab_success_rate") -> None:
    with session_scope() as session:
        session.add(
            KPIDefinition(
                kpi_name=kpi_name,
                display_name=f"Display {kpi_name}",
                unit="percent",
                description="KPI description",
                formula="a / b",
                direction_preference="higher_is_better",
                warning_threshold=97.0,
                critical_threshold=95.0,
                data_type="kpi",
                valid_min=0.0,
                valid_max=100.0,
            )
        )


def test_knowledge_api_versioning_and_approval_flow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "knowledge-api.sqlite3"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        _config_content(f"sqlite:///{database_path.as_posix()}"),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "rkaa.infrastructure.data_store.database.load_settings",
        lambda: load_settings(config_path),
    )
    initialize_database()
    Base.metadata.create_all(get_engine())
    _seed_kpi_definition()

    client = TestClient(app, raise_server_exceptions=False)

    create_response = client.post(
        "/api/v1/knowledge",
        json={
            "kpi_name": "erab_success_rate",
            "meaning_increase": "Higher success rate means healthier service.",
            "meaning_decrease": "Lower success rate means degraded service.",
            "common_causes_increase": ["parameter tuning", "traffic balancing"],
            "common_causes_decrease": ["congestion", "coverage issue"],
            "related_kpis": ["rrc_success_rate", "drop_call_rate"],
            "created_by": "analyst-a",
            "created_at": "2026-07-11T09:00:00Z",
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["version"] == 1
    assert created["status"] == "draft"

    first_approve = client.post(f"/api/v1/knowledge/{created['id']}/approve")
    assert first_approve.status_code == 200
    assert first_approve.json()["status"] == "approved"

    update_response = client.put(
        f"/api/v1/knowledge/{created['id']}",
        json={
            "meaning_increase": "Higher success rate means stable accessibility.",
            "meaning_decrease": "Lower success rate means service accessibility risk.",
            "common_causes_increase": ["parameter tuning"],
            "common_causes_decrease": ["congestion", "backhaul issue"],
            "related_kpis": ["rrc_success_rate"],
            "created_by": "analyst-b",
            "created_at": "2026-07-11T10:00:00Z",
        },
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["kpi_name"] == "erab_success_rate"
    assert updated["version"] == 2
    assert updated["status"] == "draft"
    assert updated["meaning_increase"] == "Higher success rate means stable accessibility."

    second_approve = client.post(f"/api/v1/knowledge/{updated['id']}/approve")
    assert second_approve.status_code == 200
    assert second_approve.json()["status"] == "approved"
    assert second_approve.json()["version"] == 2

    get_response = client.get("/api/v1/knowledge/by-kpi/erab_success_rate")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == updated["id"]
    assert get_response.json()["status"] == "approved"
    assert get_response.json()["created_by"] == "analyst-b"

    with session_scope() as session:
        versions = KnowledgeEntryRepository(session).list_versions("erab_success_rate")

    assert [entry.version for entry in versions] == [1, 2]
    assert [entry.status for entry in versions] == ["deprecated", "approved"]


def test_knowledge_api_returns_not_found_when_no_approved_version_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "knowledge-api-missing.sqlite3"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        _config_content(f"sqlite:///{database_path.as_posix()}"),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "rkaa.infrastructure.data_store.database.load_settings",
        lambda: load_settings(config_path),
    )
    initialize_database()
    Base.metadata.create_all(get_engine())
    _seed_kpi_definition()

    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/api/v1/knowledge/by-kpi/erab_success_rate")

    assert response.status_code == 404
    assert response.json()["error_code"] == "NOT_FOUND"


def test_knowledge_api_rejects_approving_deprecated_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "knowledge-api-deprecated.sqlite3"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        _config_content(f"sqlite:///{database_path.as_posix()}"),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "rkaa.infrastructure.data_store.database.load_settings",
        lambda: load_settings(config_path),
    )
    initialize_database()
    Base.metadata.create_all(get_engine())
    _seed_kpi_definition()

    client = TestClient(app, raise_server_exceptions=False)

    first = client.post(
        "/api/v1/knowledge",
        json={
            "kpi_name": "erab_success_rate",
            "meaning_increase": "Higher success rate means healthier service.",
            "meaning_decrease": "Lower success rate means degraded service.",
            "common_causes_increase": ["parameter tuning"],
            "common_causes_decrease": ["congestion"],
            "related_kpis": ["rrc_success_rate"],
            "created_by": "analyst-a",
        },
    )
    first_id = first.json()["id"]
    client.post(f"/api/v1/knowledge/{first_id}/approve")

    second = client.put(
        f"/api/v1/knowledge/{first_id}",
        json={
            "meaning_increase": "Higher success rate means better accessibility.",
            "meaning_decrease": "Lower success rate means accessibility degradation.",
            "common_causes_increase": ["optimization"],
            "common_causes_decrease": ["coverage issue"],
            "related_kpis": ["drop_call_rate"],
            "created_by": "analyst-b",
        },
    )
    second_id = second.json()["id"]
    client.post(f"/api/v1/knowledge/{second_id}/approve")

    response = client.post(
        f"/api/v1/knowledge/{first_id}/approve",
        headers={"X-Correlation-ID": "corr-knowledge"},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_INPUT"
    assert response.json()["correlation_id"] == "corr-knowledge"
    assert "Deprecated knowledge entries cannot be approved." in response.json()["message"]
