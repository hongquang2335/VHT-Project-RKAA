"""API endpoints for KPI CSV imports."""

from __future__ import annotations

from fastapi import APIRouter, Request

from rkaa.core.exceptions import AppError
from rkaa.domain.data_collector.csv_parser import CSVParseError, parse_kpi_csv_bytes
from rkaa.domain.data_collector.import_service import import_kpi_rows

router = APIRouter(prefix="/api/v1/kpi-records", tags=["kpi-records"])


@router.post("/import")
async def import_kpi_records(request: Request) -> dict[str, int]:
    try:
        rows = parse_kpi_csv_bytes(
            await request.body(),
            source_name=request.headers.get("X-Upload-Filename", "<upload>"),
        )
    except CSVParseError as exc:
        raise AppError(
            "Invalid KPI CSV input.",
            error_code="INVALID_INPUT",
            details={"reason": str(exc)},
        ) from exc

    return import_kpi_rows(rows).to_dict()
