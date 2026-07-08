from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rkaa.core.exceptions import NotFoundError
from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.models.kpi_record import KPIRecord
from rkaa.infrastructure.data_store.repositories.kpi_record import KPIRecordRepository


def _make_kpi_record(
    *,
    ne_id: str = "NE-001",
    kpi_name: str = "availability",
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    value: float = 99.5,
) -> KPIRecord:
    start = start_time or datetime(2026, 7, 7, 0, 0, tzinfo=UTC)
    end = end_time or (start + timedelta(minutes=15))
    return KPIRecord(
        ne_id=ne_id,
        kpi_name=kpi_name,
        start_time=start,
        end_time=end,
        value=value,
        quality_flag="good",
        is_noise=False,
        noise_reason=None,
    )


def test_create_and_get_by_id() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = KPIRecordRepository(session)
        created = repository.create(_make_kpi_record())
        session.commit()

        loaded = repository.get_by_id(created.id)

    assert created.id > 0
    assert loaded.kpi_name == "availability"


def test_bulk_create_persists_multiple_records() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    start = datetime(2026, 7, 7, 0, 0, tzinfo=UTC)
    records = [
        _make_kpi_record(start_time=start),
        _make_kpi_record(start_time=start + timedelta(minutes=15), value=98.0),
    ]

    with Session(engine) as session:
        repository = KPIRecordRepository(session)
        created = repository.bulk_create(records)
        assert len(created) == 2
        assert all(record.id > 0 for record in created)
        session.commit()


def test_find_by_ne_kpi_time_range_returns_sorted_results() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    start = datetime(2026, 7, 7, 0, 0, tzinfo=UTC)
    with Session(engine) as session:
        repository = KPIRecordRepository(session)
        repository.bulk_create(
            [
                _make_kpi_record(start_time=start + timedelta(minutes=15), value=98.0),
                _make_kpi_record(start_time=start, value=99.5),
                _make_kpi_record(ne_id="NE-002", start_time=start, value=88.0),
            ]
        )
        session.commit()

        results = repository.find_by_ne_kpi_time_range(
            ne_id="NE-001",
            kpi_name="availability",
            start_time=start,
            end_time=start + timedelta(hours=1),
        )

    assert [record.value for record in results] == [99.5, 98.0]


def test_mark_as_noise_updates_flags() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = KPIRecordRepository(session)
        created = repository.create(_make_kpi_record())
        session.commit()

        updated = repository.mark_as_noise(created.id, "outlier")
        assert updated.is_noise is True
        assert updated.noise_reason == "outlier"
        session.commit()


def test_get_by_id_raises_not_found() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = KPIRecordRepository(session)

        with pytest.raises(NotFoundError, match="KPI record '404' not found."):
            repository.get_by_id(404)


def test_mark_as_noise_raises_not_found() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = KPIRecordRepository(session)

        with pytest.raises(NotFoundError, match="KPI record '404' not found."):
            repository.mark_as_noise(404, "missing")


def test_bulk_create_surfaces_duplicate_constraint_errors() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    start = datetime(2026, 7, 7, 0, 0, tzinfo=UTC)
    duplicate_records = [
        _make_kpi_record(start_time=start),
        _make_kpi_record(start_time=start, value=90.0),
    ]

    with Session(engine) as session:
        repository = KPIRecordRepository(session)

        with pytest.raises(IntegrityError):
            repository.bulk_create(duplicate_records)
