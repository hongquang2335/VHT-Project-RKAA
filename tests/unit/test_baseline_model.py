from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.models import Baseline, KPIDefinition


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


def test_baseline_model_creates_expected_columns() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)

    Base.metadata.create_all(engine)
    inspector = inspect(engine)

    assert {column["name"] for column in inspector.get_columns("baselines")} == {
        "id",
        "ne_id",
        "kpi_name",
        "day_period",
        "week_profile",
        "mean_value",
        "median_value",
        "std_value",
        "p5_value",
        "p95_value",
        "sample_count",
        "clean_day_count",
        "required_day_count",
        "confidence_status",
        "computed_at",
    }


def test_baseline_model_persists_grouped_statistics_and_confidence() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        kpi_definition = _make_kpi_definition()
        session.add(kpi_definition)
        session.flush()

        baseline = Baseline(
            ne_id="NE-001",
            kpi_name=kpi_definition.kpi_name,
            day_period="busy",
            week_profile="weekday",
            mean_value=98.7,
            median_value=98.9,
            std_value=0.8,
            p5_value=97.4,
            p95_value=99.5,
            sample_count=56,
            clean_day_count=14,
            required_day_count=14,
            confidence_status="reliable",
            computed_at=datetime(2026, 7, 9, 8, 0, tzinfo=UTC),
        )
        session.add(baseline)
        session.commit()

    with Session(engine) as session:
        created = session.query(Baseline).one()

    assert created.ne_id == "NE-001"
    assert created.kpi_name == "erab_success_rate"
    assert created.day_period == "busy"
    assert created.week_profile == "weekday"
    assert created.mean_value == 98.7
    assert created.median_value == 98.9
    assert created.std_value == 0.8
    assert created.p5_value == 97.4
    assert created.p95_value == 99.5
    assert created.sample_count == 56
    assert created.clean_day_count == 14
    assert created.required_day_count == 14
    assert created.confidence_status == "reliable"
    assert created.computed_at.replace(tzinfo=UTC) == datetime(2026, 7, 9, 8, 0, tzinfo=UTC)
