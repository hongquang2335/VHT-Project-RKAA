from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rkaa.core.config import load_settings
from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.database import get_engine, initialize_database, session_scope
from rkaa.infrastructure.data_store.models import NetworkElement
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


def _seed_network_element(ne_id: str = "NE-001") -> None:
    with session_scope() as session:
        session.add(
            NetworkElement(
                ne_id=ne_id,
                ne_name=f"Node {ne_id}",
                vendor="VendorX",
                technology="LTE",
                region="HCM",
                site_id=f"SITE-{ne_id}",
                metadata_json={"source": "test"},
            )
        )


def test_impact_api_create_get_update_delete_flow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "impact-api.sqlite3"
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
    _seed_network_element("NE-001")
    _seed_network_element("NE-002")

    client = TestClient(app, raise_server_exceptions=False)

    create_response = client.post(
        "/api/v1/impacts",
        json={
            "ne_id": "NE-001",
            "t1": "2026-07-08T00:00:00Z",
            "t2": None,
            "impact_type": "capacity_degradation",
            "description": "Detected impact",
            "operator": "ops",
            "source": "manual",
            "status": "draft",
        },
    )

    assert create_response.status_code == 200
    impact_id = create_response.json()["id"]
    assert create_response.json()["t2"] is None

    get_response = client.get(f"/api/v1/impacts/{impact_id}")
    assert get_response.status_code == 200
    assert get_response.json()["ne_id"] == "NE-001"

    update_response = client.put(
        f"/api/v1/impacts/{impact_id}",
        json={
            "ne_id": "NE-002",
            "t1": "2026-07-08T01:00:00Z",
            "t2": "2026-07-08T01:45:00Z",
            "description": "Moved impact scope",
            "status": "confirmed",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["ne_id"] == "NE-002"
    assert update_response.json()["status"] == "confirmed"
    assert update_response.json()["description"] == "Moved impact scope"

    delete_response = client.delete(f"/api/v1/impacts/{impact_id}")
    assert delete_response.status_code == 204

    missing_response = client.get(f"/api/v1/impacts/{impact_id}")
    assert missing_response.status_code == 404
    assert missing_response.json()["error_code"] == "NOT_FOUND"


def test_impact_api_rejects_invalid_status_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "impact-transition.sqlite3"
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
    _seed_network_element("NE-001")

    client = TestClient(app, raise_server_exceptions=False)
    create_response = client.post(
        "/api/v1/impacts",
        json={
            "ne_id": "NE-001",
            "t1": "2026-07-08T00:00:00Z",
            "t2": "2026-07-08T00:30:00Z",
            "impact_type": "capacity_degradation",
            "description": "Detected impact",
            "operator": "ops",
            "source": "manual",
            "status": "draft",
        },
    )
    impact_id = create_response.json()["id"]

    response = client.put(
        f"/api/v1/impacts/{impact_id}",
        json={"status": "analyzed"},
        headers={"X-Correlation-ID": "corr-impact"},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_INPUT"
    assert response.json()["correlation_id"] == "corr-impact"
    assert "transition" in response.json()["message"]
