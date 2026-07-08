"""Repository for KPIRecord persistence operations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from rkaa.core.exceptions import NotFoundError
from rkaa.infrastructure.data_store.models.kpi_record import KPIRecord


class KPIRecordRepository:
    """CRUD and time-series queries for KPI records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, kpi_record: KPIRecord) -> KPIRecord:
        self._session.add(kpi_record)
        self._session.flush()
        self._session.refresh(kpi_record)
        return kpi_record

    def bulk_create(self, kpi_records: list[KPIRecord]) -> list[KPIRecord]:
        self._session.add_all(kpi_records)
        self._session.flush()
        for record in kpi_records:
            self._session.refresh(record)
        return kpi_records

    def get_by_id(self, record_id: int) -> KPIRecord:
        kpi_record = self._session.get(KPIRecord, record_id)
        if kpi_record is None:
            raise NotFoundError(f"KPI record '{record_id}' not found.")
        return kpi_record

    def find_by_ne_kpi_time_range(
        self,
        *,
        ne_id: str,
        kpi_name: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[KPIRecord]:
        statement = (
            select(KPIRecord)
            .where(KPIRecord.ne_id == ne_id)
            .where(KPIRecord.kpi_name == kpi_name)
            .where(KPIRecord.start_time >= start_time)
            .where(KPIRecord.start_time < end_time)
            .order_by(KPIRecord.start_time)
        )
        return list(self._session.scalars(statement))

    def mark_as_noise(self, record_id: int, reason: str) -> KPIRecord:
        kpi_record = self.get_by_id(record_id)
        kpi_record.is_noise = True
        kpi_record.noise_reason = reason
        self._session.flush()
        self._session.refresh(kpi_record)
        return kpi_record
