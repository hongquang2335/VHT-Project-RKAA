from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.models import ImpactEvent


def _make_impact_event(
    *,
    source: str = "manual",
    status: str = "draft",
    t1: datetime | None = None,
    t2: datetime | None = None,
) -> ImpactEvent:
    start = t1 or datetime(2026, 7, 8, 0, 0, tzinfo=UTC)
    return ImpactEvent(
        ne_id="NE-001",
        t1=start,
        t2=t2,
        impact_type="capacity_degradation",
        description="Detected impact",
        operator="ops",
        source=source,
        status=status,
    )


def test_impact_event_model_creates_expected_columns() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)

    Base.metadata.create_all(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("impact_events")}

    assert columns == {
        "id",
        "ne_id",
        "t1",
        "t2",
        "impact_type",
        "description",
        "operator",
        "source",
        "status",
        "created_at",
        "updated_at",
    }


def test_impact_event_accepts_ongoing_event_with_null_t2() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_impact_event(t2=None, source="cli", status="confirmed"))
        session.commit()

    with Session(engine) as session:
        created = session.query(ImpactEvent).one()

    assert created.t2 is None
    assert created.source == "cli"
    assert created.status == "confirmed"
    assert created.created_at is not None
    assert created.updated_at is not None


def test_impact_event_rejects_invalid_source() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_impact_event(source="system"))

        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        else:
            raise AssertionError("Expected invalid source to violate the check constraint.")


def test_impact_event_rejects_invalid_status() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_impact_event(status="open"))

        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        else:
            raise AssertionError("Expected invalid status to violate the check constraint.")


def test_impact_event_rejects_t2_not_after_t1() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    start = datetime(2026, 7, 8, 0, 0, tzinfo=UTC)
    with Session(engine) as session:
        session.add(_make_impact_event(t1=start, t2=start - timedelta(minutes=5)))

        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        else:
            raise AssertionError("Expected invalid t2 ordering to violate the check constraint.")
