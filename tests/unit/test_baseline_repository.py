from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rkaa.core.exceptions import NotFoundError
from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.models import Baseline, KPIDefinition
from rkaa.infrastructure.data_store.repositories.baseline import BaselineRepository


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


def _make_baseline(
    *,
    ne_id: str = "NE-001",
    kpi_name: str = "erab_success_rate",
    day_period: str = "busy",
    week_profile: str = "weekday",
    mean_value: float = 98.7,
    computed_at: datetime | None = None,
) -> Baseline:
    return Baseline(
        ne_id=ne_id,
        kpi_name=kpi_name,
        day_period=day_period,
        week_profile=week_profile,
        mean_value=mean_value,
        median_value=98.9,
        std_value=0.8,
        p5_value=97.4,
        p95_value=99.5,
        sample_count=56,
        clean_day_count=14,
        required_day_count=14,
        confidence_status="reliable",
        computed_at=computed_at or datetime(2026, 7, 9, 8, 0, tzinfo=UTC),
    )


def test_upsert_inserts_and_get_by_key_loads_baseline() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_kpi_definition())
        session.flush()

        repository = BaselineRepository(session)
        created = repository.upsert(_make_baseline())
        session.commit()

        loaded = repository.get_by_key(
            ne_id="NE-001",
            kpi_name="erab_success_rate",
            day_period="busy",
            week_profile="weekday",
        )

    assert created.id > 0
    assert loaded.mean_value == 98.7


def test_upsert_updates_existing_bucket_instead_of_inserting_duplicate() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_kpi_definition())
        session.flush()

        repository = BaselineRepository(session)
        first = repository.upsert(_make_baseline(mean_value=98.7))
        updated = repository.upsert(
            _make_baseline(
                mean_value=96.2,
                computed_at=datetime(2026, 7, 10, 8, 0, tzinfo=UTC),
            )
        )
        session.commit()

        results = repository.list_by_ne_kpi(ne_id="NE-001", kpi_name="erab_success_rate")

    assert updated.id == first.id
    assert len(results) == 1
    assert results[0].mean_value == 96.2
    assert results[0].computed_at.replace(tzinfo=UTC) == datetime(2026, 7, 10, 8, 0, tzinfo=UTC)


def test_list_by_ne_kpi_returns_matching_buckets_only() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_kpi_definition())
        session.flush()

        repository = BaselineRepository(session)
        repository.upsert(_make_baseline(day_period="transition", week_profile="weekday"))
        repository.upsert(_make_baseline(day_period="busy", week_profile="weekend"))
        repository.upsert(_make_baseline(ne_id="NE-002"))
        session.commit()

        results = repository.list_by_ne_kpi(ne_id="NE-001", kpi_name="erab_success_rate")

    assert [(item.week_profile, item.day_period) for item in results] == [
        ("weekday", "transition"),
        ("weekend", "busy"),
    ]


def test_delete_removes_existing_bucket() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_kpi_definition())
        session.flush()

        repository = BaselineRepository(session)
        repository.upsert(_make_baseline())
        session.commit()

        repository.delete(
            ne_id="NE-001",
            kpi_name="erab_success_rate",
            day_period="busy",
            week_profile="weekday",
        )
        session.commit()

        with pytest.raises(NotFoundError):
            repository.get_by_key(
                ne_id="NE-001",
                kpi_name="erab_success_rate",
                day_period="busy",
                week_profile="weekday",
            )


def test_get_by_key_raises_not_found_for_missing_bucket() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = BaselineRepository(session)

        with pytest.raises(
            NotFoundError,
            match="Baseline 'NE-404/erab_success_rate/busy/weekday' not found.",
        ):
            repository.get_by_key(
                ne_id="NE-404",
                kpi_name="erab_success_rate",
                day_period="busy",
                week_profile="weekday",
            )
