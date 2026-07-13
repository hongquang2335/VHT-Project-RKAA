from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rkaa.core.exceptions import NotFoundError
from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.models import KnowledgeEntry, KPIDefinition
from rkaa.infrastructure.data_store.repositories.knowledge_entry import KnowledgeEntryRepository


def _make_kpi_definition(*, kpi_name: str = "erab_success_rate") -> KPIDefinition:
    return KPIDefinition(
        kpi_name=kpi_name,
        display_name=f"Display {kpi_name}",
        unit="percent",
        description="KPI description",
        formula="a / b",
        direction_preference="higher_is_better",
        warning_threshold=97.0,
        critical_threshold=95.0,
        data_type="kpi",
        valid_min=0.0,
        valid_max=100.0,
    )


def _make_knowledge_entry(
    *,
    kpi_name: str = "erab_success_rate",
    version: int = 1,
    status: str = "draft",
    meaning_increase: str = "Higher success rate means healthier service.",
    related_kpis: list[str] | None = None,
) -> KnowledgeEntry:
    return KnowledgeEntry(
        kpi_name=kpi_name,
        meaning_increase=meaning_increase,
        meaning_decrease="Lower success rate means degraded service.",
        common_causes_increase=["parameter tuning", "traffic balancing"],
        common_causes_decrease=["congestion", "coverage issue"],
        related_kpis=related_kpis or ["rrc_success_rate", "drop_call_rate"],
        created_by="analyst",
        created_at=datetime(2026, 7, 11, 9, 0, tzinfo=UTC),
        version=version,
        status=status,
    )


def test_create_version_and_get_latest() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_kpi_definition())
        repository = KnowledgeEntryRepository(session)
        repository.create_version(_make_knowledge_entry(version=1))
        created = repository.create_version(_make_knowledge_entry(version=99))
        session.commit()

        loaded = repository.get_latest("erab_success_rate")

    assert created.version == 2
    assert loaded.version == 2
    assert loaded.id == created.id


def test_get_approved_returns_latest_approved_version() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_kpi_definition())
        repository = KnowledgeEntryRepository(session)
        first = repository.create_version(_make_knowledge_entry(version=1, status="approved"))
        repository.approve(first.id)
        repository.create_version(_make_knowledge_entry(version=2, status="draft"))
        third = repository.create_version(_make_knowledge_entry(version=3, status="approved"))
        repository.approve(third.id)
        session.commit()

        approved = repository.get_approved("erab_success_rate")

    assert approved.version == 3
    assert approved.status == "approved"


def test_list_versions_returns_entries_in_version_order() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_kpi_definition())
        session.add(_make_kpi_definition(kpi_name="throughput"))
        repository = KnowledgeEntryRepository(session)
        repository.create_version(_make_knowledge_entry(version=3))
        repository.create_version(_make_knowledge_entry(version=1))
        repository.create_version(_make_knowledge_entry(version=2))
        repository.create_version(_make_knowledge_entry(kpi_name="throughput", version=1))
        session.commit()

        versions = repository.list_versions("erab_success_rate")

    assert [entry.version for entry in versions] == [1, 2, 3]


def test_create_version_increments_versions_sequentially_per_kpi() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_kpi_definition())
        session.add(_make_kpi_definition(kpi_name="throughput"))
        repository = KnowledgeEntryRepository(session)

        first = repository.create_version(_make_knowledge_entry(version=7))
        second = repository.create_version(_make_knowledge_entry(version=7))
        third = repository.create_version(_make_knowledge_entry(kpi_name="throughput", version=7))
        first_version = first.version
        second_version = second.version
        third_version = third.version
        session.commit()

    assert first_version == 1
    assert second_version == 2
    assert third_version == 1


def test_create_version_keeps_older_versions_unchanged() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_kpi_definition())
        repository = KnowledgeEntryRepository(session)

        original = repository.create_version(
            _make_knowledge_entry(
                meaning_increase="Original explanation.",
                status="approved",
            )
        )
        repository.approve(original.id)
        replacement = repository.create_version(
            _make_knowledge_entry(
                meaning_increase="Updated explanation.",
                status="draft",
            )
        )
        session.commit()

        versions = repository.list_versions("erab_success_rate")

    assert [entry.version for entry in versions] == [1, 2]
    assert original.version == 1
    assert original.meaning_increase == "Original explanation."
    assert original.status == "approved"
    assert replacement.version == 2
    assert replacement.meaning_increase == "Updated explanation."
    assert replacement.status == "draft"


def test_approve_marks_selected_version_approved_and_deprecates_previous_approved() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_kpi_definition())
        repository = KnowledgeEntryRepository(session)

        first = repository.create_version(_make_knowledge_entry())
        repository.approve(first.id)
        second = repository.create_version(_make_knowledge_entry())
        approved = repository.approve(second.id)
        session.commit()

        versions = repository.list_versions("erab_success_rate")

    assert approved.id == second.id
    assert approved.status == "approved"
    assert [entry.status for entry in versions] == ["deprecated", "approved"]


def test_deprecate_marks_entry_as_deprecated() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_kpi_definition())
        repository = KnowledgeEntryRepository(session)

        created = repository.create_version(_make_knowledge_entry())
        deprecated = repository.deprecate(created.id)
        deprecated_status = deprecated.status
        session.commit()

    assert deprecated_status == "deprecated"


def test_search_matches_text_and_related_kpis() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_kpi_definition())
        session.add(_make_kpi_definition(kpi_name="throughput"))
        repository = KnowledgeEntryRepository(session)
        repository.create_version(
            _make_knowledge_entry(
                version=1,
                meaning_increase="Higher success rate means healthier accessibility.",
            )
        )
        repository.create_version(
            _make_knowledge_entry(
                kpi_name="throughput",
                version=1,
                meaning_increase="Higher throughput means more carried traffic.",
                related_kpis=["prb_utilization"],
            )
        )
        session.commit()

        text_results = repository.search("accessibility")
        related_results = repository.search("prb_utilization")

    assert [entry.kpi_name for entry in text_results] == ["erab_success_rate"]
    assert [entry.kpi_name for entry in related_results] == ["throughput"]


def test_search_returns_empty_for_blank_query() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = KnowledgeEntryRepository(session)

        assert repository.search("   ") == []


def test_get_latest_raises_not_found_for_missing_kpi() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = KnowledgeEntryRepository(session)

        with pytest.raises(
            NotFoundError,
            match="Knowledge entry for KPI 'missing' not found.",
        ):
            repository.get_latest("missing")


def test_get_approved_raises_not_found_when_no_approved_version_exists() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_kpi_definition())
        repository = KnowledgeEntryRepository(session)
        repository.create_version(_make_knowledge_entry(status="draft"))
        session.commit()

        with pytest.raises(
            NotFoundError,
            match="Approved knowledge entry for KPI 'erab_success_rate' not found.",
        ):
            repository.get_approved("erab_success_rate")


def test_approve_raises_not_found_for_missing_entry() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = KnowledgeEntryRepository(session)

        with pytest.raises(NotFoundError, match="Knowledge entry '404' not found."):
            repository.approve(404)


def test_approve_rejects_deprecated_entry() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_make_kpi_definition())
        repository = KnowledgeEntryRepository(session)
        created = repository.create_version(_make_knowledge_entry())
        repository.deprecate(created.id)

        with pytest.raises(
            ValueError,
            match="Deprecated knowledge entries cannot be approved.",
        ):
            repository.approve(created.id)
