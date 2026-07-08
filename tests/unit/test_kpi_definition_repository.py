from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rkaa.core.exceptions import NotFoundError
from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.models.kpi_definition import KPIDefinition
from rkaa.infrastructure.data_store.repositories.kpi_definition import (
    KPIDefinitionRepository,
)


def _make_kpi_definition(
    *,
    kpi_name: str = "availability",
    direction_preference: str = "higher_is_better",
    data_type: str = "kpi",
    warning_threshold: float | None = 98.0,
    critical_threshold: float | None = 95.0,
) -> KPIDefinition:
    return KPIDefinition(
        kpi_name=kpi_name,
        display_name=f"Display {kpi_name}",
        unit="percent",
        description="KPI description",
        formula="a / b",
        direction_preference=direction_preference,
        warning_threshold=warning_threshold,
        critical_threshold=critical_threshold,
        data_type=data_type,
        valid_min=0.0,
        valid_max=100.0,
    )


def test_create_and_get_by_name() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = KPIDefinitionRepository(session)
        created = repository.create(_make_kpi_definition())
        session.commit()

        loaded = repository.get_by_name("availability")

    assert created.kpi_name == "availability"
    assert loaded.display_name == "Display availability"


def test_list_returns_kpi_definitions_in_name_order() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = KPIDefinitionRepository(session)
        repository.create(_make_kpi_definition(kpi_name="throughput"))
        repository.create(_make_kpi_definition(kpi_name="availability"))
        session.commit()

        results = repository.list()

    assert [item.kpi_name for item in results] == ["availability", "throughput"]


def test_update_changes_existing_kpi_definition() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = KPIDefinitionRepository(session)
        repository.create(_make_kpi_definition())
        session.commit()

        updated = repository.update(
            "availability",
            display_name="Availability KPI",
            data_type="counter",
        )
        assert updated.display_name == "Availability KPI"
        assert updated.data_type == "counter"
        session.commit()


def test_delete_removes_existing_kpi_definition() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = KPIDefinitionRepository(session)
        repository.create(_make_kpi_definition())
        session.commit()

        repository.delete("availability")
        session.commit()

        with pytest.raises(NotFoundError):
            repository.get_by_name("availability")


def test_duplicate_kpi_name_raises_integrity_error() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = KPIDefinitionRepository(session)
        repository.create(_make_kpi_definition())
        session.commit()

        with pytest.raises(IntegrityError):
            repository.create(_make_kpi_definition())


def test_invalid_direction_preference_raises_integrity_error() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = KPIDefinitionRepository(session)

        with pytest.raises(IntegrityError):
            repository.create(
                _make_kpi_definition(direction_preference="invalid-direction")
            )


def test_equal_thresholds_raise_integrity_error() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = KPIDefinitionRepository(session)

        with pytest.raises(IntegrityError):
            repository.create(
                _make_kpi_definition(
                    warning_threshold=95.0,
                    critical_threshold=95.0,
                )
            )


def test_get_by_name_raises_not_found() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = KPIDefinitionRepository(session)

        with pytest.raises(NotFoundError, match="KPI definition 'missing' not found."):
            repository.get_by_name("missing")
