from __future__ import annotations

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.models import KPIDefinition


def _make_kpi_definition(
    *,
    kpi_name: str = "availability",
    direction_preference: str = "higher_is_better",
    data_type: str = "kpi",
) -> KPIDefinition:
    return KPIDefinition(
        kpi_name=kpi_name,
        display_name="Availability",
        unit="percent",
        description="Cell availability",
        formula="available_time / total_time",
        direction_preference=direction_preference,
        warning_threshold=98.0,
        critical_threshold=95.0,
        data_type=data_type,
        valid_min=0.0,
        valid_max=100.0,
    )


def test_kpi_definition_model_creates_expected_columns() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)

    Base.metadata.create_all(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("kpi_definitions")}

    assert columns == {
        "kpi_name",
        "display_name",
        "unit",
        "description",
        "formula",
        "direction_preference",
        "warning_threshold",
        "critical_threshold",
        "data_type",
        "valid_min",
        "valid_max",
    }


def test_kpi_definition_accepts_allowed_enums() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            _make_kpi_definition(
                kpi_name="throughput",
                direction_preference="context_dependent",
                data_type="counter",
            )
        )
        session.commit()

    with Session(engine) as session:
        created = session.get(KPIDefinition, "throughput")

    assert created is not None
    assert created.direction_preference == "context_dependent"
    assert created.data_type == "counter"


def test_kpi_definition_rejects_invalid_direction_preference() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_kpi_definition(direction_preference="invalid"))

        with Session(engine) as _:
            pass

        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        else:
            raise AssertionError(
                "Expected invalid direction_preference to violate the check constraint."
            )


def test_kpi_definition_rejects_invalid_data_type() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_kpi_definition(data_type="ratio"))

        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        else:
            raise AssertionError("Expected invalid data_type to violate the check constraint.")
