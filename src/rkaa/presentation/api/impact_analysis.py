"""API endpoints for impact analysis execution and retrieval."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from rkaa.domain.impact_analysis_service import analyze_and_store_impact
from rkaa.infrastructure.data_store.database import session_scope
from rkaa.infrastructure.data_store.repositories.impact_analysis import ImpactAnalysisRepository
from rkaa.infrastructure.data_store.repositories.impact_event import ImpactEventRepository
from rkaa.infrastructure.data_store.repositories.kpi_definition import KPIDefinitionRepository
from rkaa.infrastructure.data_store.repositories.kpi_record import KPIRecordRepository

router = APIRouter(tags=["impact-analyses"])


class ImpactAnalysisCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kpi_names: list[str]
    pre_window_hours: int
    recovery_buffer_hours: int
    post_window_hours: int = 2
    alpha: float = 0.05
    primary_test: Literal["welch", "mann_whitney"] = "welch"
    analyzed_at: datetime | None = None


class KPIDeltaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    analysis_id: int
    kpi_name: str
    pre_mean: float
    post_mean: float
    delta_abs: float
    delta_pct: float
    p_value: float | None
    change_direction: str
    anomaly_flag: str
    severity: str
    anomaly_reasons: list[str]


class ImpactAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    impact_event_id: int
    analyzed_at: datetime
    analysis_window: str
    summary: dict[str, Any] | None
    overall_assessment: str
    deltas: list[KPIDeltaResponse]


@router.post("/api/v1/impacts/{impact_id}/analyze", response_model=ImpactAnalysisResponse)
def analyze_impact(impact_id: int, payload: ImpactAnalysisCreateRequest) -> ImpactAnalysisResponse:
    with session_scope() as session:
        result = analyze_and_store_impact(
            impacts=ImpactEventRepository(session),
            analyses=ImpactAnalysisRepository(session),
            kpi_definitions=KPIDefinitionRepository(session),
            kpi_records=KPIRecordRepository(session),
            impact_event_id=impact_id,
            kpi_names=payload.kpi_names,
            pre_window_hours=payload.pre_window_hours,
            recovery_buffer_hours=payload.recovery_buffer_hours,
            post_window_hours=payload.post_window_hours,
            alpha=payload.alpha,
            primary_test=payload.primary_test,
            analyzed_at=payload.analyzed_at,
        )

    return ImpactAnalysisResponse(
        **_analysis_payload(result.analysis),
        deltas=[_delta_payload(delta) for delta in result.deltas],
    )


@router.get("/api/v1/analyses/{analysis_id}", response_model=ImpactAnalysisResponse)
def get_analysis(analysis_id: int) -> ImpactAnalysisResponse:
    with session_scope() as session:
        repository = ImpactAnalysisRepository(session)
        analysis = repository.get_by_id(analysis_id)
        deltas = repository.list_deltas_by_analysis_id(analysis_id)

    return ImpactAnalysisResponse(
        **_analysis_payload(analysis),
        deltas=[_delta_payload(delta) for delta in deltas],
    )


def _analysis_payload(analysis: object) -> dict[str, Any]:
    return {
        "id": getattr(analysis, "id"),
        "impact_event_id": getattr(analysis, "impact_event_id"),
        "analyzed_at": getattr(analysis, "analyzed_at"),
        "analysis_window": getattr(analysis, "analysis_window"),
        "summary": getattr(analysis, "summary"),
        "overall_assessment": getattr(analysis, "overall_assessment"),
    }


def _delta_payload(delta: object) -> KPIDeltaResponse:
    return KPIDeltaResponse.model_validate(
        {
            "id": getattr(delta, "id"),
            "analysis_id": getattr(delta, "analysis_id"),
            "kpi_name": getattr(delta, "kpi_name"),
            "pre_mean": getattr(delta, "pre_mean"),
            "post_mean": getattr(delta, "post_mean"),
            "delta_abs": getattr(delta, "delta_abs"),
            "delta_pct": getattr(delta, "delta_pct"),
            "p_value": getattr(delta, "p_value"),
            "change_direction": getattr(delta, "change_direction"),
            "anomaly_flag": getattr(delta, "anomaly_flag"),
            "severity": getattr(delta, "severity"),
            "anomaly_reasons": getattr(delta, "anomaly_reasons"),
        }
    )
