"""Kết nối và khởi tạo SQLite metadata cho FR-103/FR-202."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def create_sqlite_connection(database_path: str | Path) -> sqlite3.Connection:
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def _column_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row["name"]) for row in rows}


def _migrate_impact_event_for_fr202(connection: sqlite3.Connection) -> None:
    """Bổ sung cột FR-202 cho database FR-103 cũ mà không mất dữ liệu.

    ``exclude_from_baseline`` để NULL cho record legacy. Giá trị NULL cho phép
    FR-201 tiếp tục áp dụng danh sách ``excluded_impact_types`` cũ; record mới
    FR-202 sẽ ghi 0/1 rõ ràng.
    """

    columns = _column_names(connection, "impact_event")
    if not columns:
        return

    if "event_category" not in columns:
        connection.execute(
            "ALTER TABLE impact_event "
            "ADD COLUMN event_category TEXT NOT NULL DEFAULT 'IMPACT'"
        )
    if "exclude_from_baseline" not in columns:
        connection.execute(
            "ALTER TABLE impact_event ADD COLUMN exclude_from_baseline INTEGER"
        )


def initialize_metadata_schema(connection: sqlite3.Connection) -> None:
    """Tạo/migrate metadata schema cho FR-103 và FR-202."""

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS impact_event (
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
            deleted_at_utc TEXT,
            event_category TEXT NOT NULL DEFAULT 'IMPACT',
            exclude_from_baseline INTEGER,

            CHECK (source IN ('MANUAL')),
            CHECK (status IN ('ONGOING', 'CLOSED', 'DELETED')),
            CHECK (event_category IN ('IMPACT', 'MAINTENANCE', 'SPECIAL_EVENT')),
            CHECK (exclude_from_baseline IS NULL OR exclude_from_baseline IN (0, 1)),
            CHECK (t2_utc IS NULL OR t2_utc > t1_utc),
            CHECK (
                status = 'DELETED'
                OR (status = 'ONGOING' AND t2_utc IS NULL)
                OR (status = 'CLOSED' AND t2_utc IS NOT NULL)
            )
        );
        """
    )

    _migrate_impact_event_for_fr202(connection)

    connection.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_impact_event_ne_time
        ON impact_event(ne_id, t1_utc, t2_utc);

        CREATE INDEX IF NOT EXISTS idx_impact_event_cell_time
        ON impact_event(cell_id, t1_utc, t2_utc);

        CREATE INDEX IF NOT EXISTS idx_impact_event_status
        ON impact_event(status);

        CREATE INDEX IF NOT EXISTS idx_impact_event_category_time
        ON impact_event(event_category, t1_utc, t2_utc);

        CREATE INDEX IF NOT EXISTS idx_impact_event_baseline_exclusion
        ON impact_event(exclude_from_baseline, t1_utc, t2_utc);
        """
    )
    connection.commit()
