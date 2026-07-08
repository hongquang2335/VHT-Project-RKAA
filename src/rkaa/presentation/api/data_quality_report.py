"""API endpoint for data quality reporting."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from rkaa.domain.noise_filter.data_quality_report import (
    DataQualityKPIDefinition,
    DataQualityRecord,
    build_data_quality_report,
)

router = APIRouter(prefix="/api/v1/data-quality", tags=["data-quality"])


class DataQualityRecordPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ne_id: str
    kpi_name: str
    start_time: datetime
    value: float | None


class DataQualityKPIDefinitionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_type: str
    valid_min: float | None = None
    valid_max: float | None = None


class DataQualityReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[DataQualityRecordPayload]
    kpi_definition: DataQualityKPIDefinitionPayload
    granularity_minutes: int | None = None
    iqr_multiplier: float = 1.5
    sentinel_values: list[float | str] = []


class DataQualityReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completeness: float
    missing_intervals: int
    duplicate_count: int
    invalid_count: int
    noise_ratio: float
    counter_reset_count: int


@router.post("/report", response_model=DataQualityReportResponse)
def generate_data_quality_report(
    payload: DataQualityReportRequest,
) -> DataQualityReportResponse:
    report = build_data_quality_report(
        records=[
            DataQualityRecord(
                ne_id=record.ne_id,
                kpi_name=record.kpi_name,
                start_time=record.start_time,
                value=record.value,
            )
            for record in payload.records
        ],
        kpi_definition=DataQualityKPIDefinition(
            data_type=payload.kpi_definition.data_type,
            valid_min=payload.kpi_definition.valid_min,
            valid_max=payload.kpi_definition.valid_max,
        ),
        granularity_minutes=payload.granularity_minutes,
        iqr_multiplier=payload.iqr_multiplier,
        sentinel_values=payload.sentinel_values,
    )
    return DataQualityReportResponse.model_validate(report.to_dict())
