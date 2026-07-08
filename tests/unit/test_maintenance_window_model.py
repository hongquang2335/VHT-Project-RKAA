from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.models import MaintenanceWindow


def _make_maintenance_window(
    *,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> MaintenanceWindow:
    start = start_time or datetime(2026, 7, 8, 1, 0, tzinfo=UTC)
    end = end_time or (start + timedelta(hours=2))
    return MaintenanceWindow(
        ne_id="NE-001",
        start_time=start,
        end_time=end,
        event_type="software_upgrade",
        description="Planned maintenance",
        created_by="ops",
    )


def test_maintenance_window_model_creates_expected_columns() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)

    Base.metadata.create_all(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("maintenance_windows")}

    assert columns == {
        "id",
        "ne_id",
        "start_time",
        "end_time",
        "event_type",
        "description",
        "created_by",
    }


def test_maintenance_window_accepts_valid_values() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_maintenance_window())
        session.commit()

    with Session(engine) as session:
        created = session.query(MaintenanceWindow).one()

    assert created.ne_id == "NE-001"
    assert created.event_type == "software_upgrade"
    assert created.end_time > created.start_time
