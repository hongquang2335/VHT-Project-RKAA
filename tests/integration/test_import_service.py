from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select

from rkaa.core.config import load_settings
from rkaa.domain.data_collector.import_service import import_kpi_rows
from rkaa.domain.data_collector.schemas import KPIInputRow
from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.database import get_engine, initialize_database, session_scope
from rkaa.infrastructure.data_store.models import KPIRecord


def _config_content(database_url: str) -> str:
    return f"""
app:
  name: "RKAA Test"
  timezone: "UTC"
  granularity_minutes: 15
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


def _make_row(timestamp: str, period_end: str, kpi_name: str, value: str) -> KPIInputRow:
    return KPIInputRow.model_validate(
        {
            "timestamp": timestamp,
            "period_end": period_end,
            "ne_id": "NE-001",
            "kpi_name": kpi_name,
            "value": value,
            "unit": "percent",
            "quality_flag": "good",
        }
    )


def test_import_kpi_rows_inserts_batch_into_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "import.sqlite3"
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

    rows = [
        _make_row(
            "2026-07-08T00:00:00+07:00",
            "2026-07-08T00:15:00+07:00",
            "erab_success_rate",
            "98.7",
        ),
        _make_row(
            "2026-07-08T00:15:00+07:00",
            "2026-07-08T00:30:00+07:00",
            "rrc_success_rate",
            "99.1",
        ),
    ]

    summary = import_kpi_rows(rows, batch_size=2)

    with session_scope() as session:
        record_count = session.execute(select(func.count()).select_from(KPIRecord)).scalar_one()

    assert summary.to_dict() == {"total": 2, "inserted": 2, "duplicates": 0, "invalid": 0}
    assert record_count == 2


def test_import_kpi_rows_skips_duplicates_and_keeps_valid_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "duplicates.sqlite3"
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

    rows = [
        _make_row(
            "2026-07-08T00:00:00+07:00",
            "2026-07-08T00:15:00+07:00",
            "erab_success_rate",
            "98.7",
        ),
        _make_row(
            "2026-07-08T00:00:00+07:00",
            "2026-07-08T00:15:00+07:00",
            "erab_success_rate",
            "98.7",
        ),
        _make_row(
            "2026-07-08T00:15:00+07:00",
            "2026-07-08T00:30:00+07:00",
            "rrc_success_rate",
            "99.1",
        ),
    ]

    summary = import_kpi_rows(rows, batch_size=3)

    with session_scope() as session:
        persisted = list(session.scalars(select(KPIRecord).order_by(KPIRecord.start_time)))

    assert summary.to_dict() == {"total": 3, "inserted": 2, "duplicates": 1, "invalid": 0}
    assert len(persisted) == 2
    assert persisted[0].kpi_name == "erab_success_rate"
    assert persisted[1].kpi_name == "rrc_success_rate"
