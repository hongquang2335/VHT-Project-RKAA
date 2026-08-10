from dataclasses import replace
from datetime import datetime, timedelta, timezone
from time import perf_counter

from rkaa.domain.impact_manager.models import (
    ImpactEvent,
    ImpactSource,
    ImpactStatus,
)
from rkaa.infrastructure.data_store.database import (
    create_sqlite_connection,
    initialize_metadata_schema,
)
from rkaa.infrastructure.data_store.impact_repository import (
    SQLiteImpactRepository,
    datetime_from_storage,
    datetime_to_storage,
)


def build_event(impact_id: str = "impact-001") -> ImpactEvent:
    now = datetime(2026, 7, 15, 9, 50, tzinfo=timezone.utc)
    return ImpactEvent(
        impact_id=impact_id,
        ne_id="gHM00001",
        cell_id="gHM00001_30",
        t1_utc=now,
        t2_utc=None,
        impact_type="NE_RESTART",
        description="Khởi động lại NE",
        operator="engineer_a",
        source=ImpactSource.MANUAL,
        status=ImpactStatus.ONGOING,
        created_at_utc=now,
        updated_at_utc=now,
        deleted_at_utc=None,
    )


def test_datetime_storage_uses_space_and_preserves_timezone() -> None:
    value = datetime(2026, 7, 15, 9, 50, tzinfo=timezone.utc)
    stored = datetime_to_storage(value)

    assert stored == "2026-07-15 09:50:00+00:00"
    assert datetime_from_storage(stored) == value


def test_event_survives_database_reopen(tmp_path) -> None:
    database_path = tmp_path / "metadata.db"

    first_connection = create_sqlite_connection(database_path)
    initialize_metadata_schema(first_connection)
    first_repository = SQLiteImpactRepository(first_connection)
    first_repository.create(build_event())
    first_connection.close()

    second_connection = create_sqlite_connection(database_path)
    initialize_metadata_schema(second_connection)
    second_repository = SQLiteImpactRepository(second_connection)
    loaded = second_repository.get_by_id("impact-001")
    second_connection.close()

    assert loaded is not None
    assert loaded.ne_id == "gHM00001"
    assert loaded.status is ImpactStatus.ONGOING


def test_list_update_and_soft_delete(tmp_path) -> None:
    connection = create_sqlite_connection(tmp_path / "metadata.db")
    initialize_metadata_schema(connection)
    repository = SQLiteImpactRepository(connection)

    first = repository.create(build_event("impact-001"))
    repository.create(replace(build_event("impact-002"), ne_id="gHM00002"))

    listed = repository.list_events(ne_id="gHM00001")
    assert [event.impact_id for event in listed] == ["impact-001"]

    closed = replace(
        first,
        t2_utc=first.t1_utc + timedelta(minutes=30),
        status=ImpactStatus.CLOSED,
        description="Đã kết thúc restart",
        updated_at_utc=first.updated_at_utc + timedelta(minutes=30),
    )
    updated = repository.update(closed)
    assert updated.status is ImpactStatus.CLOSED
    assert updated.description == "Đã kết thúc restart"

    deleted_at = updated.updated_at_utc + timedelta(minutes=1)
    assert repository.soft_delete(updated.impact_id, deleted_at) is True
    assert repository.get_by_id(updated.impact_id) is None

    deleted = repository.get_by_id(updated.impact_id, include_deleted=True)
    assert deleted is not None
    assert deleted.status is ImpactStatus.DELETED
    assert deleted.deleted_at_utc == deleted_at
    connection.close()


def test_sqlite_create_completes_within_two_seconds(tmp_path) -> None:
    connection = create_sqlite_connection(tmp_path / "metadata.db")
    initialize_metadata_schema(connection)
    repository = SQLiteImpactRepository(connection)

    started = perf_counter()
    repository.create(build_event())
    elapsed = perf_counter() - started

    connection.close()
    assert elapsed <= 2.0


def test_fr202_fields_survive_database_reopen(tmp_path) -> None:
    from rkaa.domain.impact_manager.models import EventCategory

    database_path = tmp_path / "metadata.db"
    connection = create_sqlite_connection(database_path)
    initialize_metadata_schema(connection)
    repository = SQLiteImpactRepository(connection)
    event = replace(
        build_event("maintenance-001"),
        event_category=EventCategory.MAINTENANCE,
        exclude_from_baseline=True,
    )
    repository.create(event)
    connection.close()

    connection = create_sqlite_connection(database_path)
    initialize_metadata_schema(connection)
    loaded = SQLiteImpactRepository(connection).get_by_id("maintenance-001")
    connection.close()

    assert loaded is not None
    assert loaded.event_category is EventCategory.MAINTENANCE
    assert loaded.exclude_from_baseline is True


def test_initialize_schema_migrates_legacy_fr103_database(tmp_path) -> None:
    database_path = tmp_path / "legacy.db"
    connection = create_sqlite_connection(database_path)
    connection.execute(
        """
        CREATE TABLE impact_event (
            impact_id TEXT PRIMARY KEY,
            ne_id TEXT NOT NULL,
            cell_id TEXT,
            t1_utc TEXT NOT NULL,
            t2_utc TEXT,
            impact_type TEXT NOT NULL,
            description TEXT NOT NULL,
            operator TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            deleted_at_utc TEXT
        )
        """
    )
    connection.commit()

    initialize_metadata_schema(connection)
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(impact_event)").fetchall()
    }
    connection.close()

    assert "event_category" in columns
    assert "exclude_from_baseline" in columns
