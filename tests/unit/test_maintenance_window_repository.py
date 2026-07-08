from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rkaa.core.exceptions import NotFoundError
from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.models.maintenance_window import MaintenanceWindow
from rkaa.infrastructure.data_store.repositories.maintenance_window import (
    MaintenanceWindowRepository,
)


def _make_maintenance_window(
    *,
    ne_id: str = "NE-001",
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    event_type: str = "software_upgrade",
) -> MaintenanceWindow:
    start = start_time or datetime(2026, 7, 8, 1, 0, tzinfo=UTC)
    end = end_time or (start + timedelta(hours=2))
    return MaintenanceWindow(
        ne_id=ne_id,
        start_time=start,
        end_time=end,
        event_type=event_type,
        description="Planned maintenance",
        created_by="ops",
    )


def test_create_and_get_by_id() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = MaintenanceWindowRepository(session)
        created = repository.create(_make_maintenance_window())
        session.commit()

        loaded = repository.get_by_id(created.id)

    assert created.id > 0
    assert loaded.event_type == "software_upgrade"


def test_list_returns_windows_sorted_by_start_time() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    start = datetime(2026, 7, 8, 1, 0, tzinfo=UTC)
    with Session(engine) as session:
        repository = MaintenanceWindowRepository(session)
        repository.create(
            _make_maintenance_window(
                start_time=start + timedelta(hours=3),
                event_type="power_adjustment",
            )
        )
        repository.create(
            _make_maintenance_window(
                start_time=start,
                event_type="software_upgrade",
            )
        )
        session.commit()

        results = repository.list()

    assert [window.event_type for window in results] == [
        "software_upgrade",
        "power_adjustment",
    ]


def test_update_changes_existing_maintenance_window() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = MaintenanceWindowRepository(session)
        created = repository.create(_make_maintenance_window())
        session.commit()

        updated = repository.update(created.id, event_type="site_visit", created_by="noc")
        assert updated.event_type == "site_visit"
        assert updated.created_by == "noc"
        session.commit()


def test_delete_removes_existing_maintenance_window() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = MaintenanceWindowRepository(session)
        created = repository.create(_make_maintenance_window())
        session.commit()

        repository.delete(created.id)
        session.commit()

        with pytest.raises(NotFoundError):
            repository.get_by_id(created.id)


def test_get_by_id_raises_not_found() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = MaintenanceWindowRepository(session)

        with pytest.raises(NotFoundError, match="Maintenance window '404' not found."):
            repository.get_by_id(404)


def test_delete_raises_not_found_for_missing_window() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = MaintenanceWindowRepository(session)

        with pytest.raises(NotFoundError, match="Maintenance window '404' not found."):
            repository.delete(404)
