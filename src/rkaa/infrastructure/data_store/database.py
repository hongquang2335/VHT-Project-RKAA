"""Kết nối và khởi tạo cơ sở dữ liệu metadata của RKAA."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def create_sqlite_connection(
    path: str | Path = "tmp/rkaa_metadata.db",
) -> sqlite3.Connection:
    """Tạo kết nối SQLite dùng để lưu metadata vận hành của RKAA."""

    database_path = Path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def initialize_metadata_schema(connection: sqlite3.Connection) -> None:
    """Tạo bảng và chỉ mục metadata của FR-103 nếu chưa tồn tại."""

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

            CHECK (source IN ('MANUAL')),
            CHECK (status IN ('ONGOING', 'CLOSED', 'DELETED')),
            CHECK (t2_utc IS NULL OR t2_utc > t1_utc),
            CHECK (
                status = 'DELETED'
                OR (status = 'ONGOING' AND t2_utc IS NULL)
                OR (status = 'CLOSED' AND t2_utc IS NOT NULL)
            )
        );

        CREATE INDEX IF NOT EXISTS idx_impact_event_ne_time
        ON impact_event(ne_id, t1_utc, t2_utc);

        CREATE INDEX IF NOT EXISTS idx_impact_event_cell_time
        ON impact_event(cell_id, t1_utc, t2_utc);

        CREATE INDEX IF NOT EXISTS idx_impact_event_status
        ON impact_event(status);
        """
    )
    connection.commit()
