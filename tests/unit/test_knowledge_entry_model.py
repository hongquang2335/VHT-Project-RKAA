from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.models import KnowledgeEntry, KPIDefinition


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


def _make_knowledge_entry(*, version: int = 1) -> KnowledgeEntry:
    return KnowledgeEntry(
        kpi_name="erab_success_rate",
        meaning_increase="Higher success rate indicates better accessibility quality.",
        meaning_decrease="Lower success rate indicates degraded accessibility quality.",
        common_causes_increase=["parameter optimization", "traffic balancing"],
        common_causes_decrease=["congestion", "radio interference"],
        related_kpis=["rrc_success_rate", "drop_call_rate"],
        created_by="analyst",
        created_at=datetime(2026, 7, 11, 8, 0, tzinfo=UTC),
        version=version,
        status="draft",
    )


def test_knowledge_entry_model_creates_expected_columns() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)

    Base.metadata.create_all(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("knowledge_entries")}

    assert columns == {
        "id",
        "kpi_name",
        "meaning_increase",
        "meaning_decrease",
        "common_causes_increase",
        "common_causes_decrease",
        "related_kpis",
        "created_by",
        "created_at",
        "version",
        "status",
    }


def test_knowledge_entry_accepts_valid_values() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_kpi_definition())
        session.add(_make_knowledge_entry())
        session.commit()

    with Session(engine) as session:
        created = session.query(KnowledgeEntry).one()

    assert created.kpi_name == "erab_success_rate"
    assert created.meaning_increase.startswith("Higher success rate")
    assert created.common_causes_increase == ["parameter optimization", "traffic balancing"]
    assert created.related_kpis == ["rrc_success_rate", "drop_call_rate"]
    assert created.version == 1
    assert created.status == "draft"


def test_knowledge_entry_rejects_duplicate_kpi_name_version() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_kpi_definition())
        session.add(_make_knowledge_entry(version=1))
        session.flush()

        session.add(_make_knowledge_entry(version=1))
        with pytest.raises(IntegrityError):
            session.flush()


def test_knowledge_entry_rejects_non_positive_version() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_kpi_definition())
        session.add(_make_knowledge_entry(version=0))

        with pytest.raises(IntegrityError):
            session.flush()
