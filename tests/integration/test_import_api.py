from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from rkaa.core.config import load_settings
from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.database import get_engine, initialize_database, session_scope
from rkaa.infrastructure.data_store.models import KPIRecord
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


def test_import_api_uploads_csv_and_returns_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "api.sqlite3"
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

    client = TestClient(app, raise_server_exceptions=False)
    csv_path = Path(__file__).resolve().parents[1] / "fixtures" / "kpi_valid.csv"

    with csv_path.open("rb") as file_handle:
        response = client.post(
            "/api/v1/kpi-records/import",
            content=file_handle.read(),
            headers={
                "Content-Type": "text/csv",
                "X-Upload-Filename": "kpi_valid.csv",
            },
        )

    with session_scope() as session:
        record_count = session.execute(select(func.count()).select_from(KPIRecord)).scalar_one()

    assert response.status_code == 200
    assert response.json() == {"total": 2, "inserted": 2, "duplicates": 0, "invalid": 0}
    assert record_count == 2


def test_import_api_returns_standard_error_for_invalid_csv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "api-invalid.sqlite3"
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

    client = TestClient(app, raise_server_exceptions=False)
    csv_path = Path(__file__).resolve().parents[1] / "fixtures" / "kpi_invalid.csv"

    with csv_path.open("rb") as file_handle:
        response = client.post(
            "/api/v1/kpi-records/import",
            content=file_handle.read(),
            headers={
                "Content-Type": "text/csv",
                "X-Upload-Filename": "kpi_invalid.csv",
                "X-Correlation-ID": "corr-import",
            },
        )

    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_INPUT"
    assert response.json()["message"] == "Invalid KPI CSV input."
    assert response.json()["correlation_id"] == "corr-import"
    assert "reason" in response.json()["details"]
