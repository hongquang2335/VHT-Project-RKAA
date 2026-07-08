from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.models import KPIRecord


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


def test_kpi_record_model_creates_expected_columns() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)

    Base.metadata.create_all(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("kpi_records")}

    assert columns == {
        "id",
        "ne_id",
        "kpi_name",
        "start_time",
        "end_time",
        "value",
        "quality_flag",
        "is_noise",
        "noise_reason",
    }


def test_kpi_record_accepts_valid_time_range_and_numeric_value() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_kpi_record())
        session.commit()

    with Session(engine) as session:
        created = session.query(KPIRecord).one()

    assert created.start_time.tzinfo is None or created.start_time.tzinfo == UTC
    assert created.end_time > created.start_time
    assert isinstance(created.value, float)


def test_kpi_record_rejects_end_time_before_start_time() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    start = datetime(2026, 7, 7, 1, 0, tzinfo=UTC)
    end = start - timedelta(minutes=15)

    with Session(engine) as session:
        session.add(_make_kpi_record(start_time=start, end_time=end))

        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        else:
            raise AssertionError("Expected invalid time range to violate the check constraint.")


def test_kpi_record_rejects_duplicate_ne_kpi_start_time() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    start = datetime(2026, 7, 7, 0, 0, tzinfo=UTC)

    with Session(engine) as session:
        session.add(_make_kpi_record(start_time=start))
        session.commit()

        session.add(_make_kpi_record(start_time=start, value=88.0))

        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        else:
            raise AssertionError("Expected duplicate record key to violate the unique constraint.")
