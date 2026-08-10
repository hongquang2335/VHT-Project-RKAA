"""Triển khai lưu trữ Impact Event bằng SQLite."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from rkaa.domain.impact_manager.models import (
    ImpactEvent,
    ImpactSource,
    ImpactStatus,
)


_EVENT_COLUMNS = """
    impact_id,
    ne_id,
    cell_id,
    t1_utc,
    t2_utc,
    impact_type,
    description,
    operator,
    source,
    status,
    created_at_utc,
    updated_at_utc,
    deleted_at_utc
"""


def datetime_to_storage(value: datetime | None) -> str | None:
    """Chuyển ``datetime`` có timezone thành chuỗi UTC không chứa chữ ``T``."""

    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("Datetime lưu vào database phải có timezone")

    utc_value = value.astimezone(timezone.utc)
    return utc_value.isoformat(sep=" ", timespec="seconds")


def datetime_from_storage(value: str | None) -> datetime | None:
    """Chuyển chuỗi thời gian SQLite thành ``datetime`` UTC có timezone."""

    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"Datetime trong database không có timezone: {value!r}")
    return parsed.astimezone(timezone.utc)


def _required_datetime(value: str | None, field_name: str) -> datetime:
    parsed = datetime_from_storage(value)
    if parsed is None:
        raise ValueError(f"Database thiếu trường datetime bắt buộc: {field_name}")
    return parsed


def row_to_impact_event(row: sqlite3.Row) -> ImpactEvent:
    """Chuyển một dòng SQLite thành mô hình nghiệp vụ ``ImpactEvent``."""

    return ImpactEvent(
        impact_id=str(row["impact_id"]),
        ne_id=str(row["ne_id"]),
        cell_id=row["cell_id"],
        t1_utc=_required_datetime(row["t1_utc"], "t1_utc"),
        t2_utc=datetime_from_storage(row["t2_utc"]),
        impact_type=str(row["impact_type"]),
        description=str(row["description"]),
        operator=str(row["operator"]),
        source=ImpactSource(str(row["source"])),
        status=ImpactStatus(str(row["status"])),
        created_at_utc=_required_datetime(row["created_at_utc"], "created_at_utc"),
        updated_at_utc=_required_datetime(row["updated_at_utc"], "updated_at_utc"),
        deleted_at_utc=datetime_from_storage(row["deleted_at_utc"]),
    )


class SQLiteImpactRepository:
    """Lớp triển khai giao diện ``ImpactRepository`` bằng SQLite."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        if connection.row_factory is not sqlite3.Row:
            connection.row_factory = sqlite3.Row
        self.connection = connection

    def create(self, event: ImpactEvent) -> ImpactEvent:
        sql = f"""
            INSERT INTO impact_event ({_EVENT_COLUMNS})
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = self._event_params(event)

        try:
            self.connection.execute(sql, params)
            self.connection.commit()
        except sqlite3.IntegrityError as exc:
            self.connection.rollback()
            raise ValueError(
                f"Không thể tạo Impact Event {event.impact_id}: {exc}"
            ) from exc
        except sqlite3.DatabaseError:
            self.connection.rollback()
            raise

        created = self.get_by_id(event.impact_id, include_deleted=True)
        if created is None:
            raise RuntimeError("Đã INSERT nhưng không đọc lại được Impact Event")
        return created

    def get_by_id(
        self,
        impact_id: str,
        *,
        include_deleted: bool = False,
    ) -> ImpactEvent | None:
        sql = f"""
            SELECT {_EVENT_COLUMNS}
            FROM impact_event
            WHERE impact_id = ?
        """
        params: list[object] = [impact_id]
        if not include_deleted:
            sql += " AND status <> 'DELETED'"

        row = self.connection.execute(sql, params).fetchone()
        return None if row is None else row_to_impact_event(row)

    def list_events(
        self,
        *,
        ne_id: str | None = None,
        cell_id: str | None = None,
        status: ImpactStatus | None = None,
        include_deleted: bool = False,
    ) -> list[ImpactEvent]:
        sql = f"""
            SELECT {_EVENT_COLUMNS}
            FROM impact_event
        """
        conditions: list[str] = []
        params: list[object] = []

        if ne_id is not None:
            conditions.append("ne_id = ?")
            params.append(ne_id)
        if cell_id is not None:
            conditions.append("cell_id = ?")
            params.append(cell_id)
        if status is not None:
            conditions.append("status = ?")
            params.append(status.value)
        if not include_deleted:
            conditions.append("status <> 'DELETED'")

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY t1_utc DESC, created_at_utc DESC"

        rows = self.connection.execute(sql, params).fetchall()
        return [row_to_impact_event(row) for row in rows]

    def update(self, event: ImpactEvent) -> ImpactEvent:
        sql = """
            UPDATE impact_event
            SET
                ne_id = ?,
                cell_id = ?,
                t1_utc = ?,
                t2_utc = ?,
                impact_type = ?,
                description = ?,
                operator = ?,
                source = ?,
                status = ?,
                created_at_utc = ?,
                updated_at_utc = ?,
                deleted_at_utc = ?
            WHERE impact_id = ?
        """
        params = (
            event.ne_id,
            event.cell_id,
            datetime_to_storage(event.t1_utc),
            datetime_to_storage(event.t2_utc),
            event.impact_type,
            event.description,
            event.operator,
            event.source.value,
            event.status.value,
            datetime_to_storage(event.created_at_utc),
            datetime_to_storage(event.updated_at_utc),
            datetime_to_storage(event.deleted_at_utc),
            event.impact_id,
        )

        try:
            cursor = self.connection.execute(sql, params)
            if cursor.rowcount == 0:
                self.connection.rollback()
                raise LookupError(f"Không tìm thấy impact_id={event.impact_id}")
            self.connection.commit()
        except sqlite3.IntegrityError as exc:
            self.connection.rollback()
            raise ValueError(
                f"Không thể cập nhật Impact Event {event.impact_id}: {exc}"
            ) from exc
        except sqlite3.DatabaseError:
            self.connection.rollback()
            raise

        updated = self.get_by_id(event.impact_id, include_deleted=True)
        if updated is None:
            raise RuntimeError("Đã UPDATE nhưng không đọc lại được Impact Event")
        return updated

    def soft_delete(
        self,
        impact_id: str,
        deleted_at_utc: datetime,
    ) -> bool:
        stored_deleted_at = datetime_to_storage(deleted_at_utc)
        sql = """
            UPDATE impact_event
            SET
                status = 'DELETED',
                deleted_at_utc = ?,
                updated_at_utc = ?
            WHERE impact_id = ?
              AND status <> 'DELETED'
        """

        try:
            cursor = self.connection.execute(
                sql,
                (stored_deleted_at, stored_deleted_at, impact_id),
            )
            self.connection.commit()
        except sqlite3.DatabaseError:
            self.connection.rollback()
            raise

        return cursor.rowcount > 0

    @staticmethod
    def _event_params(event: ImpactEvent) -> tuple[object, ...]:
        return (
            event.impact_id,
            event.ne_id,
            event.cell_id,
            datetime_to_storage(event.t1_utc),
            datetime_to_storage(event.t2_utc),
            event.impact_type,
            event.description,
            event.operator,
            event.source.value,
            event.status.value,
            datetime_to_storage(event.created_at_utc),
            datetime_to_storage(event.updated_at_utc),
            datetime_to_storage(event.deleted_at_utc),
        )
