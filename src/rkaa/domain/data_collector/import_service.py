"""Import service for KPI CSV data."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy.exc import IntegrityError

from rkaa.domain.data_collector.schemas import KPIInputRow
from rkaa.infrastructure.data_store.database import session_scope
from rkaa.infrastructure.data_store.models.kpi_record import KPIRecord
from rkaa.infrastructure.data_store.repositories.kpi_record import KPIRecordRepository


@dataclass(slots=True)
class KPIImportSummary:
    """Aggregated result of a KPI import run."""

    total: int
    inserted: int
    duplicates: int
    invalid: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _to_model(row: KPIInputRow) -> KPIRecord:
    return KPIRecord(
        ne_id=row.ne_id,
        kpi_name=row.kpi_name,
        start_time=row.timestamp,
        end_time=row.period_end,
        value=row.value,
        quality_flag=row.quality_flag,
    )


def _is_duplicate_error(exc: IntegrityError) -> bool:
    message = str(exc.orig).lower() if exc.orig is not None else str(exc).lower()
    return "unique constraint" in message or "unique failed" in message


def import_kpi_rows(rows: list[KPIInputRow], *, batch_size: int = 500) -> KPIImportSummary:
    """Import parsed KPI rows into the database with duplicate skipping."""

    summary = KPIImportSummary(
        total=len(rows),
        inserted=0,
        duplicates=0,
        invalid=0,
    )

    with session_scope() as session:
        repository = KPIRecordRepository(session)

        for start_index in range(0, len(rows), batch_size):
            batch = rows[start_index : start_index + batch_size]

            try:
                with session.begin_nested():
                    repository.bulk_create([_to_model(row) for row in batch])
                summary.inserted += len(batch)
                continue
            except IntegrityError:
                pass

            for row in batch:
                try:
                    with session.begin_nested():
                        repository.create(_to_model(row))
                    summary.inserted += 1
                except IntegrityError as exc:
                    if _is_duplicate_error(exc):
                        summary.duplicates += 1
                    else:
                        summary.invalid += 1

    return summary
