"""Orchestrate end-to-end impact analysis and persist the result."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import fmean
from types import SimpleNamespace
from typing import Literal

from rkaa.domain.anomaly_aggregation import aggregate_anomaly_results
from rkaa.domain.baseline_statistics import compute_baseline_statistics
from rkaa.domain.delta_calculator import calculate_delta
from rkaa.domain.impact_classifier import classify_impact
from rkaa.domain.impact_data_loader import ImpactDataLoadResult, load_impact_kpi_samples
from rkaa.domain.impact_service import update_impact_event_status
from rkaa.domain.mann_whitney_test import run_mann_whitney_u_test
from rkaa.domain.three_sigma_detector import detect_three_sigma_anomaly
from rkaa.domain.threshold_detector import detect_threshold_anomaly
from rkaa.domain.welch_test import run_welch_t_test
from rkaa.domain.zscore_detector import detect_zscore_anomaly
from rkaa.infrastructure.data_store.models import ImpactAnalysis, KPIDelta
from rkaa.infrastructure.data_store.models.impact_event import ImpactEvent
from rkaa.infrastructure.data_store.models.kpi_definition import KPIDefinition
from rkaa.infrastructure.data_store.repositories.impact_analysis import ImpactAnalysisRepository
from rkaa.infrastructure.data_store.repositories.impact_event import ImpactEventRepository
from rkaa.infrastructure.data_store.repositories.kpi_definition import KPIDefinitionRepository
from rkaa.infrastructure.data_store.repositories.kpi_record import KPIRecordRepository

PrimaryTest = Literal["welch", "mann_whitney"]


@dataclass(frozen=True, slots=True)
class ImpactAnalysisRunResult:
    """Represents one persisted impact analysis run and its KPI deltas."""

    analysis: ImpactAnalysis
    deltas: list[KPIDelta]


def analyze_and_store_impact(
    *,
    impacts: ImpactEventRepository,
    analyses: ImpactAnalysisRepository,
    kpi_definitions: KPIDefinitionRepository,
    kpi_records: KPIRecordRepository,
    impact_event_id: int,
    kpi_names: list[str],
    pre_window_hours: int,
    recovery_buffer_hours: int,
    post_window_hours: int = 2,
    alpha: float = 0.05,
    primary_test: PrimaryTest = "welch",
    analyzed_at: datetime | None = None,
) -> ImpactAnalysisRunResult:
    """Run one complete impact-analysis workflow and persist the result."""

    impact_event = impacts.get_by_id(impact_event_id)
    resolved_analyzed_at = analyzed_at or datetime.now(UTC)

    delta_payloads: list[dict[str, object]] = []
    summary_items: list[dict[str, object]] = []

    for kpi_name in kpi_names:
        kpi_definition = kpi_definitions.get_by_name(kpi_name)
        loaded = load_impact_kpi_samples(
            impact_event=impact_event,
            kpi_name=kpi_name,
            repository=kpi_records,
            pre_window_hours=pre_window_hours,
            recovery_buffer_hours=recovery_buffer_hours,
            post_window_hours=post_window_hours,
        )
        delta_payload, summary_item = _analyze_one_kpi(
            impact_event=impact_event,
            kpi_definition=kpi_definition,
            loaded=loaded,
            primary_test=primary_test,
            alpha=alpha,
        )
        delta_payloads.append(delta_payload)
        summary_items.append(summary_item)

    classification_counts = Counter(
        str(summary_item["classification"]) for summary_item in summary_items
    )
    analysis = analyses.create(
        ImpactAnalysis(
            impact_event_id=impact_event.id,
            analyzed_at=resolved_analyzed_at,
            analysis_window=(
                f"pre={pre_window_hours}h,recovery={recovery_buffer_hours}h,post={post_window_hours}h"
            ),
            summary={
                "primary_test": primary_test,
                "kpi_results": summary_items,
                "classification_counts": dict(classification_counts),
            },
            overall_assessment=_overall_assessment(classification_counts),
        )
    )
    deltas = analyses.bulk_create_deltas(
        [
            KPIDelta(
                analysis_id=analysis.id,
                kpi_name=str(payload["kpi_name"]),
                pre_mean=float(payload["pre_mean"]),
                post_mean=float(payload["post_mean"]),
                delta_abs=float(payload["delta_abs"]),
                delta_pct=float(payload["delta_pct"]),
                p_value=payload["p_value"],
                change_direction=str(payload["change_direction"]),
                anomaly_flag=str(payload["anomaly_flag"]),
                severity=str(payload["severity"]),
                anomaly_reasons=list(payload["anomaly_reasons"]),
            )
            for payload in delta_payloads
        ]
    )
    update_impact_event_status(
        impacts=impacts,
        event_id=impact_event.id,
        status="analyzed",
    )
    return ImpactAnalysisRunResult(analysis=analysis, deltas=deltas)


def _analyze_one_kpi(
    *,
    impact_event: ImpactEvent,
    kpi_definition: KPIDefinition,
    loaded: ImpactDataLoadResult,
    primary_test: PrimaryTest,
    alpha: float,
) -> tuple[dict[str, object], dict[str, object]]:
    pre_records = loaded.pre_window.records
    post_records = loaded.post_window.records
    pre_mean = fmean(record.value for record in pre_records) if pre_records else 0.0
    post_mean = fmean(record.value for record in post_records) if post_records else 0.0

    if pre_records and post_records:
        delta = calculate_delta(pre_samples=pre_records, post_samples=post_records)
        delta_abs = delta.delta_abs
        delta_pct = delta.delta_pct
    else:
        delta_abs = post_mean - pre_mean
        delta_pct = 0.0 if pre_mean == 0 else (delta_abs / pre_mean) * 100

    has_sufficient_data = (
        loaded.pre_window.status == "ready" and loaded.post_window.status == "ready"
    )
    welch_result = _safe_run_welch(pre_records=pre_records, post_records=post_records, alpha=alpha)
    mann_whitney_result = _safe_run_mann_whitney(
        pre_records=pre_records,
        post_records=post_records,
        alpha=alpha,
    )
    primary_result = welch_result if primary_test == "welch" else mann_whitney_result
    is_significant = bool(primary_result and primary_result["is_significant"])

    classification = classify_impact(
        kpi_definition=kpi_definition,
        delta_abs=delta_abs,
        is_significant=is_significant,
        has_sufficient_data=has_sufficient_data,
    ).classification
    anomaly_result = _detect_anomaly(
        kpi_definition=kpi_definition,
        pre_records=pre_records,
        post_mean=post_mean,
        has_post_records=bool(post_records),
    )
    anomaly_flag = "anomalous" if anomaly_result.is_anomaly else anomaly_result.severity

    return (
        {
            "kpi_name": kpi_definition.kpi_name,
            "pre_mean": pre_mean,
            "post_mean": post_mean,
            "delta_abs": delta_abs,
            "delta_pct": delta_pct,
            "p_value": None if primary_result is None else primary_result["p_value"],
            "change_direction": _change_direction(delta_abs),
            "anomaly_flag": anomaly_flag,
            "severity": anomaly_result.severity,
            "anomaly_reasons": anomaly_result.reasons,
        },
        {
            "kpi_name": kpi_definition.kpi_name,
            "classification": classification,
            "pre_completeness": loaded.pre_window.completeness,
            "post_completeness": loaded.post_window.completeness,
            "pre_status": loaded.pre_window.status,
            "post_status": loaded.post_window.status,
            "welch": welch_result,
            "mann_whitney": mann_whitney_result,
            "primary_test": primary_test,
            "primary_p_value": None if primary_result is None else primary_result["p_value"],
            "is_significant": is_significant,
            "impact_ne_id": impact_event.ne_id,
            "anomaly_flag": anomaly_flag,
            "severity": anomaly_result.severity,
            "anomaly_reasons": anomaly_result.reasons,
        },
    )


def _detect_anomaly(
    *,
    kpi_definition: KPIDefinition,
    pre_records: list[object],
    post_mean: float,
    has_post_records: bool,
):
    if not has_post_records:
        return aggregate_anomaly_results()

    threshold_result = detect_threshold_anomaly(value=post_mean, kpi_definition=kpi_definition)
    if not pre_records:
        return aggregate_anomaly_results(threshold_result=threshold_result)

    baseline_statistics = compute_baseline_statistics(record.value for record in pre_records)
    baseline = SimpleNamespace(
        mean_value=baseline_statistics.mean,
        std_value=baseline_statistics.std,
    )
    zscore_result = detect_zscore_anomaly(value=post_mean, baseline=baseline)
    three_sigma_result = detect_three_sigma_anomaly(
        value=post_mean,
        baseline=baseline,
    )
    return aggregate_anomaly_results(
        threshold_result=threshold_result,
        zscore_result=zscore_result,
        three_sigma_result=three_sigma_result,
    )


def _safe_run_welch(
    *,
    pre_records: list[object],
    post_records: list[object],
    alpha: float,
) -> dict[str, object] | None:
    try:
        result = run_welch_t_test(
            pre_samples=pre_records,
            post_samples=post_records,
            alpha=alpha,
        )
    except ValueError:
        return None

    return {
        "statistic": result.statistic,
        "p_value": result.p_value,
        "is_significant": result.is_significant,
    }


def _safe_run_mann_whitney(
    *,
    pre_records: list[object],
    post_records: list[object],
    alpha: float,
) -> dict[str, object] | None:
    try:
        result = run_mann_whitney_u_test(
            pre_samples=pre_records,
            post_samples=post_records,
            alpha=alpha,
        )
    except ValueError:
        return None

    return {
        "statistic": result.statistic,
        "p_value": result.p_value,
        "is_significant": result.is_significant,
    }


def _change_direction(delta_abs: float) -> str:
    if delta_abs > 0:
        return "increase"
    if delta_abs < 0:
        return "decrease"
    return "stable"


def _overall_assessment(classification_counts: Counter[str]) -> str:
    if classification_counts.get("degraded", 0) > 0:
        return "degraded"
    if classification_counts.get("improved", 0) > 0:
        return "improved"
    if classification_counts and classification_counts.total() == classification_counts.get(
        "insufficient_data", 0
    ):
        return "insufficient_data"
    return "stable"
