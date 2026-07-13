from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rkaa.core.config import load_settings
from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.database import get_engine, initialize_database, session_scope
from rkaa.infrastructure.data_store.models import (
    ImpactEvent,
    KPIDefinition,
    KPIRecord,
    NetworkElement,
)
from rkaa.main import app


def _config_content(database_url: str) -> str:
    return f"""
app:
  name: "RKAA Test"
  timezone: "UTC"
  granularity_minutes: 15
  baseline_min_clean_days: 14
  anomaly_zscore_threshold: 3.0
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


def _seed_analysis_prerequisites() -> int:
    with session_scope() as session:
        session.add(
            NetworkElement(
                ne_id="NE-001",
                ne_name="Node NE-001",
                vendor="VendorX",
                technology="LTE",
                region="HCM",
                site_id="SITE-001",
                metadata_json={"source": "test"},
            )
        )
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
        impact = ImpactEvent(
            ne_id="NE-001",
            t1=datetime(2026, 7, 6, 19, 0, tzinfo=UTC),
            t2=datetime(2026, 7, 6, 20, 0, tzinfo=UTC),
            impact_type="capacity_degradation",
            description="Detected impact",
            operator="ops",
            source="manual",
            status="confirmed",
        )
        session.add(impact)
        session.flush()

        for timestamp in (
            datetime(2026, 7, 6, 17, 0, tzinfo=UTC),
            datetime(2026, 7, 6, 17, 15, tzinfo=UTC),
            datetime(2026, 7, 6, 17, 30, tzinfo=UTC),
            datetime(2026, 7, 6, 17, 45, tzinfo=UTC),
            datetime(2026, 7, 6, 18, 0, tzinfo=UTC),
            datetime(2026, 7, 6, 18, 15, tzinfo=UTC),
            datetime(2026, 7, 6, 18, 30, tzinfo=UTC),
            datetime(2026, 7, 6, 18, 45, tzinfo=UTC),
        ):
            session.add(
                KPIRecord(
                    ne_id="NE-001",
                    kpi_name="erab_success_rate",
                    start_time=timestamp,
                    end_time=_period_end(timestamp),
                    value=90.0,
                    quality_flag="good",
                    is_noise=False,
                    noise_reason=None,
                )
            )
        for timestamp in (
            datetime(2026, 7, 7, 2, 0, tzinfo=UTC),
            datetime(2026, 7, 7, 2, 15, tzinfo=UTC),
            datetime(2026, 7, 7, 2, 30, tzinfo=UTC),
            datetime(2026, 7, 7, 2, 45, tzinfo=UTC),
            datetime(2026, 7, 7, 3, 0, tzinfo=UTC),
            datetime(2026, 7, 7, 3, 15, tzinfo=UTC),
            datetime(2026, 7, 7, 3, 30, tzinfo=UTC),
            datetime(2026, 7, 7, 3, 45, tzinfo=UTC),
        ):
            session.add(
                KPIRecord(
                    ne_id="NE-001",
                    kpi_name="erab_success_rate",
                    start_time=timestamp,
                    end_time=_period_end(timestamp),
                    value=99.0,
                    quality_flag="good",
                    is_noise=False,
                    noise_reason=None,
                )
            )

        return impact.id


def _period_end(timestamp: datetime) -> datetime:
    return timestamp + timedelta(minutes=15)


def test_impact_analysis_api_analyzes_and_returns_persisted_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "impact-analysis-api.sqlite3"
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
    impact_id = _seed_analysis_prerequisites()

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        f"/api/v1/impacts/{impact_id}/analyze",
        json={
            "kpi_names": ["erab_success_rate"],
            "pre_window_hours": 2,
            "recovery_buffer_hours": 4,
            "post_window_hours": 2,
            "alpha": 0.05,
            "primary_test": "welch",
            "analyzed_at": "2026-07-07T05:00:00Z",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["impact_event_id"] == impact_id
    assert payload["overall_assessment"] == "improved"
    assert payload["summary"]["classification_counts"] == {"improved": 1}
    assert payload["deltas"][0]["kpi_name"] == "erab_success_rate"
    assert payload["deltas"][0]["pre_mean"] == 90.0
    assert payload["deltas"][0]["post_mean"] == 99.0
    assert payload["deltas"][0]["delta_abs"] == 9.0
    assert payload["deltas"][0]["delta_pct"] == 10.0
    assert payload["deltas"][0]["anomaly_flag"] == "anomalous"
    assert payload["deltas"][0]["severity"] == "anomalous"
    assert payload["deltas"][0]["anomaly_reasons"] == [
        "zscore_anomaly",
        "three_sigma_anomaly",
    ]
    assert payload["summary"]["kpi_results"][0]["anomaly_flag"] == "anomalous"


def test_impact_analysis_api_get_returns_persisted_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "impact-analysis-get.sqlite3"
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
    impact_id = _seed_analysis_prerequisites()

    client = TestClient(app, raise_server_exceptions=False)
    create_response = client.post(
        f"/api/v1/impacts/{impact_id}/analyze",
        json={
            "kpi_names": ["erab_success_rate"],
            "pre_window_hours": 2,
            "recovery_buffer_hours": 4,
            "analyzed_at": "2026-07-07T05:00:00Z",
        },
    )
    analysis_id = create_response.json()["id"]

    response = client.get(f"/api/v1/analyses/{analysis_id}")

    assert response.status_code == 200
    assert response.json()["id"] == analysis_id
    assert response.json()["impact_event_id"] == impact_id
    assert response.json()["deltas"][0]["analysis_id"] == analysis_id
    assert response.json()["deltas"][0]["severity"] == "anomalous"
    assert response.json()["deltas"][0]["anomaly_reasons"] == [
        "zscore_anomaly",
        "three_sigma_anomaly",
    ]
