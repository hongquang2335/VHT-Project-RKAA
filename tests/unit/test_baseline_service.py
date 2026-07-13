from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rkaa.core.config import DayPeriodSettings
from rkaa.domain.baseline_service import compute_and_store_baselines
from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.models import Baseline, KPIDefinition
from rkaa.infrastructure.data_store.repositories.baseline import BaselineRepository


@dataclass(frozen=True, slots=True)
class CleanBaselineRecord:
    ne_id: str
    kpi_name: str
    start_time: datetime
    value: float


def _day_periods() -> DayPeriodSettings:
    return DayPeriodSettings.model_validate(
        {
            "busy": {"start": "07:00", "end": "10:00"},
            "transition": {"start": "10:00", "end": "17:00"},
            "off_peak": {"start": "17:00", "end": "07:00"},
        }
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


def _daily_record(day_offset: int, *, value: float, minute_offset: int = 0) -> CleanBaselineRecord:
    return CleanBaselineRecord(
        ne_id="NE-001",
        kpi_name="erab_success_rate",
        start_time=datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
        + timedelta(days=day_offset, minutes=minute_offset),
        value=value,
    )


def test_compute_and_store_baselines_persists_grouped_statistics() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    records = [
        _daily_record(0, value=98.0),
        _daily_record(1, value=99.0),
        _daily_record(2, value=100.0),
        _daily_record(3, value=97.0),
        _daily_record(4, value=96.0),
        _daily_record(5, value=95.0),
        _daily_record(6, value=94.0),
        _daily_record(7, value=93.0),
        _daily_record(8, value=92.0),
        _daily_record(9, value=91.0),
        _daily_record(10, value=90.0),
        _daily_record(11, value=89.0),
        _daily_record(12, value=88.0),
        _daily_record(13, value=87.0),
    ]

    with Session(engine) as session:
        session.add(_make_kpi_definition())
        session.flush()

        result = compute_and_store_baselines(
            records,
            repository=BaselineRepository(session),
            day_periods=_day_periods(),
            required_clean_days=14,
            computed_at=datetime(2026, 7, 15, 8, 0, tzinfo=UTC),
        )
        session.commit()

        persisted = session.query(Baseline).order_by(Baseline.week_profile).all()

        persisted_summary = [
            (
                item.week_profile,
                item.sample_count,
                item.clean_day_count,
                item.confidence_status,
                item.mean_value,
                item.median_value,
                item.computed_at.replace(tzinfo=UTC),
            )
            for item in persisted
        ]

    assert len(result.baselines) == 2
    assert persisted_summary == [
        ("weekday", 10, 10, "insufficient", 93.7, 93.5, datetime(2026, 7, 15, 8, 0, tzinfo=UTC)),
        ("weekend", 4, 4, "insufficient", 93.0, 93.0, datetime(2026, 7, 15, 8, 0, tzinfo=UTC)),
    ]


def test_compute_and_store_baselines_upserts_existing_bucket() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    initial_records = [_daily_record(day, value=90.0 + day) for day in range(14)]
    updated_records = [_daily_record(day, value=80.0 + day) for day in range(14)]

    with Session(engine) as session:
        session.add(_make_kpi_definition())
        session.flush()

        repository = BaselineRepository(session)
        first = compute_and_store_baselines(
            initial_records,
            repository=repository,
            day_periods=_day_periods(),
            required_clean_days=14,
            computed_at=datetime(2026, 7, 15, 8, 0, tzinfo=UTC),
        )
        second = compute_and_store_baselines(
            updated_records,
            repository=repository,
            day_periods=_day_periods(),
            required_clean_days=14,
            computed_at=datetime(2026, 7, 16, 8, 0, tzinfo=UTC),
        )
        session.commit()

        persisted = session.query(Baseline).all()

    assert len(first.baselines) == 2
    assert len(second.baselines) == 2
    assert len(persisted) == 2
    assert {(item.week_profile, item.mean_value) for item in persisted} == {
        ("weekday", 86.3),
        ("weekend", 87.0),
    }


def test_compute_and_store_baselines_handles_multiple_group_buckets() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    records = [
        _daily_record(0, value=98.0),
        _daily_record(1, value=99.0),
        _daily_record(5, value=97.5),
        _daily_record(6, value=97.0),
        CleanBaselineRecord(
            ne_id="NE-001",
            kpi_name="erab_success_rate",
            start_time=datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
            value=95.0,
        ),
        CleanBaselineRecord(
            ne_id="NE-001",
            kpi_name="erab_success_rate",
            start_time=datetime(2026, 7, 2, 12, 0, tzinfo=UTC),
            value=96.0,
        ),
    ]

    with Session(engine) as session:
        session.add(_make_kpi_definition())
        session.flush()

        result = compute_and_store_baselines(
            records,
            repository=BaselineRepository(session),
            day_periods=_day_periods(),
            required_clean_days=3,
            computed_at=datetime(2026, 7, 15, 8, 0, tzinfo=UTC),
        )
        session.commit()

        result_keys = {(item.week_profile, item.day_period) for item in result.baselines}

    assert result_keys == {("weekday", "busy"), ("weekday", "transition")}


def test_compute_and_store_baselines_returns_empty_result_for_no_records() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        result = compute_and_store_baselines(
            [],
            repository=BaselineRepository(session),
            day_periods=_day_periods(),
            required_clean_days=14,
        )

    assert result.baselines == []
