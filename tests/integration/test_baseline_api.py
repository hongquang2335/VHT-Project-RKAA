from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rkaa.core.config import load_settings
from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.database import get_engine, initialize_database, session_scope
from rkaa.infrastructure.data_store.models import KPIDefinition
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


def _seed_kpi_definition() -> None:
    with session_scope() as session:
        session.add(
            KPIDefinition(
                kpi_name="erab_success_rate",
                display_name="ERAB Success Rate",
                unit="percent",
                description="Accessibility KPI",
                formula="success/attempt",
                direction_preference="higher_is_better",
                warning_threshold=97.0,
                critical_threshold=95.0,
                data_type="kpi",
                valid_min=0.0,
                valid_max=100.0,
            )
        )


def test_baseline_compute_api_persists_and_returns_grouped_baselines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "baseline-api.sqlite3"
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
    response = client.post(
        "/api/v1/baselines/compute",
        json={
            "records": [
                {
                    "ne_id": "NE-001",
                    "kpi_name": "erab_success_rate",
                    "start_time": "2026-07-01T08:00:00Z",
                    "value": 98.0,
                },
                {
                    "ne_id": "NE-001",
                    "kpi_name": "erab_success_rate",
                    "start_time": "2026-07-02T08:00:00Z",
                    "value": 99.0,
                },
                {
                    "ne_id": "NE-001",
                    "kpi_name": "erab_success_rate",
                    "start_time": "2026-07-04T08:00:00Z",
                    "value": 97.0,
                },
                {
                    "ne_id": "NE-001",
                    "kpi_name": "erab_success_rate",
                    "start_time": "2026-07-05T08:00:00Z",
                    "value": 95.0,
                },
            ],
            "required_clean_days": 3,
            "computed_at": "2026-07-15T08:00:00Z",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "baselines": [
            {
                "ne_id": "NE-001",
                "kpi_name": "erab_success_rate",
                "day_period": "busy",
                "week_profile": "weekday",
                "mean_value": 98.5,
                "median_value": 98.5,
                "std_value": 0.5,
                "p5_value": 98.05,
                "p95_value": 98.95,
                "sample_count": 2,
                "clean_day_count": 2,
                "required_day_count": 3,
                "confidence_status": "insufficient",
                "computed_at": "2026-07-15T08:00:00",
            },
            {
                "ne_id": "NE-001",
                "kpi_name": "erab_success_rate",
                "day_period": "busy",
                "week_profile": "weekend",
                "mean_value": 96.0,
                "median_value": 96.0,
                "std_value": 1.0,
                "p5_value": 95.1,
                "p95_value": 96.9,
                "sample_count": 2,
                "clean_day_count": 2,
                "required_day_count": 3,
                "confidence_status": "insufficient",
                "computed_at": "2026-07-15T08:00:00",
            },
        ]
    }


def test_baseline_list_api_returns_persisted_baselines_for_ne_kpi(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "baseline-list.sqlite3"
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
    client.post(
        "/api/v1/baselines/compute",
        json={
            "records": [
                {
                    "ne_id": "NE-001",
                    "kpi_name": "erab_success_rate",
                    "start_time": "2026-07-01T08:00:00Z",
                    "value": 98.0,
                },
                {
                    "ne_id": "NE-001",
                    "kpi_name": "erab_success_rate",
                    "start_time": "2026-07-02T08:00:00Z",
                    "value": 99.0,
                },
                {
                    "ne_id": "NE-001",
                    "kpi_name": "erab_success_rate",
                    "start_time": "2026-07-05T08:00:00Z",
                    "value": 95.0,
                },
            ],
            "required_clean_days": 3,
            "computed_at": "2026-07-15T08:00:00Z",
        },
    )

    response = client.get("/api/v1/baselines/NE-001/erab_success_rate")

    assert response.status_code == 200
    assert [item["week_profile"] for item in response.json()["baselines"]] == [
        "weekday",
        "weekend",
    ]
