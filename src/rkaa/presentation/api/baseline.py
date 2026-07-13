"""API endpoints for baseline computation and retrieval."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from rkaa.domain.baseline_service import compute_and_store_baselines
from rkaa.infrastructure.data_store.database import session_scope
from rkaa.infrastructure.data_store.repositories.baseline import BaselineRepository

router = APIRouter(prefix="/api/v1/baselines", tags=["baselines"])


class BaselineRecordPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ne_id: str
    kpi_name: str
    start_time: datetime
    value: float


class BaselineComputeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[BaselineRecordPayload]
    required_clean_days: int | None = None
    computed_at: datetime | None = None


class BaselineResponseItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ne_id: str
    kpi_name: str
    day_period: str
    week_profile: str
    mean_value: float
    median_value: float
    std_value: float
    p5_value: float
    p95_value: float
    sample_count: int
    clean_day_count: int
    required_day_count: int
    confidence_status: str
    computed_at: datetime


class BaselineListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baselines: list[BaselineResponseItem]


@router.post("/compute", response_model=BaselineListResponse)
def compute_baselines(payload: BaselineComputeRequest) -> BaselineListResponse:
    with session_scope() as session:
        result = compute_and_store_baselines(
            records=payload.records,
            repository=BaselineRepository(session),
            required_clean_days=payload.required_clean_days,
            computed_at=payload.computed_at,
        )

    return BaselineListResponse(
        baselines=[_to_response_item(baseline) for baseline in result.baselines]
    )


@router.get("/{ne_id}/{kpi_name}", response_model=BaselineListResponse)
def list_baselines(ne_id: str, kpi_name: str) -> BaselineListResponse:
    with session_scope() as session:
        baselines = BaselineRepository(session).list_by_ne_kpi(ne_id=ne_id, kpi_name=kpi_name)

    return BaselineListResponse(
        baselines=[_to_response_item(baseline) for baseline in baselines]
    )


def _to_response_item(baseline: object) -> BaselineResponseItem:
    return BaselineResponseItem.model_validate(
        {
            "ne_id": getattr(baseline, "ne_id"),
            "kpi_name": getattr(baseline, "kpi_name"),
            "day_period": getattr(baseline, "day_period"),
            "week_profile": getattr(baseline, "week_profile"),
            "mean_value": getattr(baseline, "mean_value"),
            "median_value": getattr(baseline, "median_value"),
            "std_value": getattr(baseline, "std_value"),
            "p5_value": getattr(baseline, "p5_value"),
            "p95_value": getattr(baseline, "p95_value"),
            "sample_count": getattr(baseline, "sample_count"),
            "clean_day_count": getattr(baseline, "clean_day_count"),
            "required_day_count": getattr(baseline, "required_day_count"),
            "confidence_status": getattr(baseline, "confidence_status"),
            "computed_at": getattr(baseline, "computed_at"),
        }
    )
