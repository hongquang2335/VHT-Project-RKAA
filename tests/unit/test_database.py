from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, UniqueConstraint, func, insert, select
from sqlalchemy.exc import IntegrityError

from rkaa.core.config import load_settings
from rkaa.infrastructure.data_store.database import (
    create_engine_from_url,
    get_engine,
    get_session_factory,
    initialize_database,
    session_scope,
)


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


def test_create_engine_supports_sqlite() -> None:
    engine = create_engine_from_url("sqlite:///./test.db")

    assert engine.dialect.name == "sqlite"


def test_initialize_database_creates_session_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "db.sqlite3"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        _config_content(f"sqlite:///{database_path.as_posix()}"),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "rkaa.infrastructure.data_store.database.load_settings",
        lambda: load_settings(config_path),
    )

    session_factory = initialize_database()

    assert session_factory is get_session_factory()
    assert get_engine().dialect.name == "sqlite"


def test_session_scope_commits_and_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "db.sqlite3"
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

    metadata = MetaData()
    sample = Table(
        "sample_records",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("value", Integer, nullable=False),
        UniqueConstraint("value", name="uq_sample_value"),
    )
    metadata.create_all(get_engine())

    with session_scope() as session:
        session.execute(insert(sample).values(value=1))

    with pytest.raises(IntegrityError):
        with session_scope() as session:
            session.execute(insert(sample).values(value=1))
            session.execute(insert(sample).values(value=1))

    with session_scope() as session:
        row_count = session.execute(select(func.count()).select_from(sample)).scalar_one()

    assert row_count == 1
