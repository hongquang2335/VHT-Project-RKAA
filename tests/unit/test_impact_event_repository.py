from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rkaa.core.exceptions import NotFoundError
from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.models.impact_event import ImpactEvent
from rkaa.infrastructure.data_store.repositories.impact_event import ImpactEventRepository


def _make_impact_event(
    *,
    ne_id: str = "NE-001",
    t1: datetime | None = None,
    t2: datetime | None = None,
    status: str = "draft",
) -> ImpactEvent:
    start = t1 or datetime(2026, 7, 8, 0, 0, tzinfo=UTC)
    return ImpactEvent(
        ne_id=ne_id,
        t1=start,
        t2=t2,
        impact_type="capacity_degradation",
        description="Detected impact",
        operator="ops",
        source="manual",
        status=status,
    )


def test_create_and_get_by_id() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = ImpactEventRepository(session)
        created = repository.create(_make_impact_event())
        session.commit()

        loaded = repository.get_by_id(created.id)

    assert created.id > 0
    assert loaded.status == "draft"


def test_list_returns_events_sorted_by_t1() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    start = datetime(2026, 7, 8, 0, 0, tzinfo=UTC)
    with Session(engine) as session:
        repository = ImpactEventRepository(session)
        repository.create(_make_impact_event(t1=start + timedelta(hours=1), status="confirmed"))
        repository.create(_make_impact_event(t1=start, status="draft"))
        session.commit()

        results = repository.list()

    assert [event.status for event in results] == ["draft", "confirmed"]


def test_update_changes_existing_impact_event() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = ImpactEventRepository(session)
        created = repository.create(_make_impact_event())
        session.commit()

        updated = repository.update(created.id, status="analyzed", operator="noc")
        assert updated.status == "analyzed"
        assert updated.operator == "noc"
        session.commit()


def test_delete_removes_existing_impact_event() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = ImpactEventRepository(session)
        created = repository.create(_make_impact_event())
        session.commit()

        repository.delete(created.id)
        session.commit()

        with pytest.raises(NotFoundError):
            repository.get_by_id(created.id)


def test_create_supports_ongoing_event_with_null_t2() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = ImpactEventRepository(session)
        created = repository.create(_make_impact_event(t2=None, status="confirmed"))
        assert created.t2 is None
        session.commit()


def test_get_by_id_raises_not_found() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = ImpactEventRepository(session)

        with pytest.raises(NotFoundError, match="Impact event '404' not found."):
            repository.get_by_id(404)


def test_delete_raises_not_found_for_missing_event() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = ImpactEventRepository(session)

        with pytest.raises(NotFoundError, match="Impact event '404' not found."):
            repository.delete(404)
