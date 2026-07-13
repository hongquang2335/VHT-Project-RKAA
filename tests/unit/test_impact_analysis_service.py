from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rkaa.domain.impact_analysis_service import analyze_and_store_impact
from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.models import ImpactAnalysis, KPIDelta
from rkaa.infrastructure.data_store.models.impact_event import ImpactEvent
from rkaa.infrastructure.data_store.models.kpi_definition import KPIDefinition
from rkaa.infrastructure.data_store.models.kpi_record import KPIRecord
from rkaa.infrastructure.data_store.models.network_element import NetworkElement
from rkaa.infrastructure.data_store.repositories.impact_analysis import ImpactAnalysisRepository
from rkaa.infrastructure.data_store.repositories.impact_event import ImpactEventRepository
from rkaa.infrastructure.data_store.repositories.kpi_definition import KPIDefinitionRepository
from rkaa.infrastructure.data_store.repositories.kpi_record import KPIRecordRepository
from rkaa.infrastructure.data_store.repositories.network_element import (
    NetworkElementRepository,
)


def _network_element() -> NetworkElement:
    return NetworkElement(
        ne_id="NE-001",
        ne_name="Node 1",
        vendor="VendorX",
        technology="LTE",
        region="HCM",
        site_id="SITE-001",
        metadata_json={"source": "test"},
    )


def _impact_event(*, status: str = "confirmed") -> ImpactEvent:
    return ImpactEvent(
        ne_id="NE-001",
        t1=datetime(2026, 7, 6, 19, 0, tzinfo=UTC),
        t2=datetime(2026, 7, 6, 20, 0, tzinfo=UTC),
        impact_type="capacity_degradation",
        description="Detected impact",
        operator="ops",
        source="manual",
        status=status,
    )


def _kpi_definition(*, direction_preference: str = "higher_is_better") -> KPIDefinition:
    if direction_preference == "lower_is_better":
        warning_threshold = 95.0
        critical_threshold = 97.0
    else:
        warning_threshold = 97.0
        critical_threshold = 95.0

    return KPIDefinition(
        kpi_name="erab_success_rate",
        display_name="ERAB Success Rate",
        unit="percent",
        description="Accessibility KPI",
        formula="success/attempt",
        direction_preference=direction_preference,
        warning_threshold=warning_threshold,
        critical_threshold=critical_threshold,
        data_type="kpi",
        valid_min=0.0,
        valid_max=100.0,
    )


def _record(start_time: datetime, value: float) -> KPIRecord:
    return KPIRecord(
        ne_id="NE-001",
        kpi_name="erab_success_rate",
        start_time=start_time,
        end_time=start_time + timedelta(minutes=15),
        value=value,
        quality_flag="good",
        is_noise=False,
        noise_reason=None,
    )


def test_analyze_and_store_impact_persists_analysis_and_marks_event_analyzed() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    pre_times = [
        datetime(2026, 7, 6, 17, minute, tzinfo=UTC)
        for minute in (0, 15, 30, 45)
    ] + [
        datetime(2026, 7, 6, 18, minute, tzinfo=UTC)
        for minute in (0, 15, 30, 45)
    ]
    post_times = [
        datetime(2026, 7, 7, 2, minute, tzinfo=UTC)
        for minute in (0, 15, 30, 45)
    ] + [
        datetime(2026, 7, 7, 3, minute, tzinfo=UTC)
        for minute in (0, 15, 30, 45)
    ]

    with Session(engine) as session:
        NetworkElementRepository(session).create(_network_element())
        impact = ImpactEventRepository(session).create(_impact_event())
        KPIDefinitionRepository(session).create(_kpi_definition())
        KPIRecordRepository(session).bulk_create(
            [_record(timestamp, 90.0) for timestamp in pre_times]
            + [_record(timestamp, 99.0) for timestamp in post_times]
        )

        result = analyze_and_store_impact(
            impacts=ImpactEventRepository(session),
            analyses=ImpactAnalysisRepository(session),
            kpi_definitions=KPIDefinitionRepository(session),
            kpi_records=KPIRecordRepository(session),
            impact_event_id=impact.id,
            kpi_names=["erab_success_rate"],
            pre_window_hours=2,
            recovery_buffer_hours=4,
            post_window_hours=2,
            analyzed_at=datetime(2026, 7, 7, 5, 0, tzinfo=UTC),
        )
        session.commit()

        persisted_analysis = session.query(ImpactAnalysis).one()
        persisted_delta = session.query(KPIDelta).one()
        persisted_impact = ImpactEventRepository(session).get_by_id(impact.id)

    assert result.analysis.id == persisted_analysis.id
    assert result.deltas[0].id == persisted_delta.id
    assert persisted_analysis.overall_assessment == "improved"
    assert persisted_analysis.summary["classification_counts"] == {"improved": 1}
    assert persisted_delta.pre_mean == 90.0
    assert persisted_delta.post_mean == 99.0
    assert persisted_delta.delta_abs == 9.0
    assert persisted_delta.delta_pct == 10.0
    assert persisted_delta.change_direction == "increase"
    assert persisted_delta.anomaly_flag == "anomalous"
    assert persisted_delta.severity == "anomalous"
    assert persisted_delta.anomaly_reasons == ["zscore_anomaly", "three_sigma_anomaly"]
    assert persisted_delta.p_value == 0.0
    assert persisted_analysis.summary["kpi_results"][0]["anomaly_flag"] == "anomalous"
    assert persisted_analysis.summary["kpi_results"][0]["severity"] == "anomalous"
    assert persisted_analysis.summary["kpi_results"][0]["anomaly_reasons"] == [
        "zscore_anomaly",
        "three_sigma_anomaly",
    ]
    assert persisted_impact.status == "analyzed"


def test_analyze_and_store_impact_persists_insufficient_data_when_windows_are_sparse() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        NetworkElementRepository(session).create(_network_element())
        impact = ImpactEventRepository(session).create(_impact_event())
        KPIDefinitionRepository(session).create(_kpi_definition(direction_preference="lower_is_better"))
        KPIRecordRepository(session).bulk_create(
            [
                _record(datetime(2026, 7, 6, 17, 0, tzinfo=UTC), 100.0),
                _record(datetime(2026, 7, 6, 17, 15, tzinfo=UTC), 101.0),
                _record(datetime(2026, 7, 7, 2, 0, tzinfo=UTC), 80.0),
            ]
        )

        analyze_and_store_impact(
            impacts=ImpactEventRepository(session),
            analyses=ImpactAnalysisRepository(session),
            kpi_definitions=KPIDefinitionRepository(session),
            kpi_records=KPIRecordRepository(session),
            impact_event_id=impact.id,
            kpi_names=["erab_success_rate"],
            pre_window_hours=2,
            recovery_buffer_hours=4,
            post_window_hours=2,
            analyzed_at=datetime(2026, 7, 7, 5, 0, tzinfo=UTC),
        )
        session.commit()

        persisted_analysis = session.query(ImpactAnalysis).one()
        persisted_delta = session.query(KPIDelta).one()

    assert persisted_analysis.overall_assessment == "insufficient_data"
    assert persisted_analysis.summary["classification_counts"] == {"insufficient_data": 1}
    assert persisted_delta.pre_mean == 100.5
    assert persisted_delta.post_mean == 80.0
    assert persisted_delta.delta_abs == -20.5
    assert persisted_delta.p_value is None
    assert persisted_delta.change_direction == "decrease"
    assert persisted_delta.anomaly_flag == "anomalous"
    assert persisted_delta.severity == "anomalous"
    assert persisted_delta.anomaly_reasons == ["zscore_anomaly", "three_sigma_anomaly"]
