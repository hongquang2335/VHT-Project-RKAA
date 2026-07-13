from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.models import (
    ImpactAnalysis,
    ImpactEvent,
    KPIDefinition,
    KPIDelta,
)


def _make_impact_event() -> ImpactEvent:
    return ImpactEvent(
        ne_id="NE-001",
        t1=datetime(2026, 7, 8, 0, 0, tzinfo=UTC),
        t2=datetime(2026, 7, 8, 0, 30, tzinfo=UTC),
        impact_type="capacity_degradation",
        description="Detected impact",
        operator="ops",
        source="manual",
        status="confirmed",
    )


def _make_kpi_definition() -> KPIDefinition:
    return KPIDefinition(
        kpi_name="erab_success_rate",
        display_name="ERAB Success Rate",
        unit="percent",
        description="Accessibility KPI",
        formula="success/attempt",
        direction_preference="higher_is_better",
        warning_threshold=97.0,
        critical_threshold=95.0,
        data_type="kpi",
        valid_min=0.0,
        valid_max=100.0,
    )


def test_analysis_models_create_expected_columns() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)

    Base.metadata.create_all(engine)
    inspector = inspect(engine)

    assert {column["name"] for column in inspector.get_columns("impact_analyses")} == {
        "id",
        "impact_event_id",
        "analyzed_at",
        "analysis_window",
        "summary",
        "overall_assessment",
    }
    assert {column["name"] for column in inspector.get_columns("kpi_deltas")} == {
        "id",
        "analysis_id",
        "kpi_name",
        "pre_mean",
        "post_mean",
        "delta_abs",
        "delta_pct",
        "p_value",
        "change_direction",
        "anomaly_flag",
        "severity",
        "anomaly_reasons",
    }


def test_analysis_models_persist_srs_fields() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        impact_event = _make_impact_event()
        kpi_definition = _make_kpi_definition()
        session.add_all([impact_event, kpi_definition])
        session.flush()

        analysis = ImpactAnalysis(
            impact_event_id=impact_event.id,
            analyzed_at=impact_event.t2 + timedelta(minutes=10),
            analysis_window="[-30m, +30m]",
            summary={"affected_cells": 3, "confidence": "high"},
            overall_assessment="Likely service degradation observed around the event window.",
        )
        session.add(analysis)
        session.flush()

        delta = KPIDelta(
            analysis_id=analysis.id,
            kpi_name=kpi_definition.kpi_name,
            pre_mean=98.7,
            post_mean=93.1,
            delta_abs=-5.6,
            delta_pct=-5.67,
            p_value=0.012,
            change_direction="decrease",
            anomaly_flag="anomalous",
            severity="critical",
            anomaly_reasons=["threshold_critical", "zscore_anomaly"],
        )
        session.add(delta)
        session.commit()

    with Session(engine) as session:
        created_analysis = session.query(ImpactAnalysis).one()
        created_delta = session.query(KPIDelta).one()

    assert created_analysis.summary == {"affected_cells": 3, "confidence": "high"}
    assert created_analysis.analysis_window == "[-30m, +30m]"
    assert created_analysis.overall_assessment.startswith("Likely service degradation")
    assert created_delta.analysis_id == created_analysis.id
    assert created_delta.kpi_name == "erab_success_rate"
    assert created_delta.pre_mean == 98.7
    assert created_delta.post_mean == 93.1
    assert created_delta.delta_abs == -5.6
    assert created_delta.delta_pct == -5.67
    assert created_delta.p_value == 0.012
    assert created_delta.change_direction == "decrease"
    assert created_delta.anomaly_flag == "anomalous"
    assert created_delta.severity == "critical"
    assert created_delta.anomaly_reasons == ["threshold_critical", "zscore_anomaly"]
