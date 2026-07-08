from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rkaa.core.exceptions import NotFoundError
from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.models.network_element import NetworkElement
from rkaa.infrastructure.data_store.repositories.network_element import (
    NetworkElementRepository,
)


def _make_network_element(ne_id: str, *, technology: str = "LTE") -> NetworkElement:
    return NetworkElement(
        ne_id=ne_id,
        ne_name=f"Node {ne_id}",
        vendor="VendorX",
        technology=technology,
        region="HCM",
        site_id=f"SITE-{ne_id}",
        metadata_json={"source": "test"},
    )


def test_create_and_get_by_id() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = NetworkElementRepository(session)
        created = repository.create(_make_network_element("NE-001"))
        session.commit()

        loaded = repository.get_by_id("NE-001")

    assert created.ne_id == "NE-001"
    assert loaded.ne_name == "Node NE-001"


def test_list_returns_network_elements_in_id_order() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = NetworkElementRepository(session)
        repository.create(_make_network_element("NE-002"))
        repository.create(_make_network_element("NE-001", technology="NR"))
        session.commit()

        results = repository.list()

    assert [item.ne_id for item in results] == ["NE-001", "NE-002"]


def test_update_changes_existing_network_element() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = NetworkElementRepository(session)
        repository.create(_make_network_element("NE-001"))
        session.commit()

        updated = repository.update("NE-001", region="HN", technology="NSA")
        assert updated.region == "HN"
        assert updated.technology == "NSA"
        session.commit()


def test_delete_removes_existing_network_element() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = NetworkElementRepository(session)
        repository.create(_make_network_element("NE-001"))
        session.commit()

        repository.delete("NE-001")
        session.commit()

        with pytest.raises(NotFoundError):
            repository.get_by_id("NE-001")


def test_duplicate_ne_id_raises_integrity_error() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = NetworkElementRepository(session)
        repository.create(_make_network_element("NE-001"))
        session.commit()

        with pytest.raises(IntegrityError):
            repository.create(_make_network_element("NE-001", technology="NR"))


def test_get_by_id_raises_not_found() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = NetworkElementRepository(session)

        with pytest.raises(NotFoundError, match="Network element 'NE-404' not found."):
            repository.get_by_id("NE-404")


def test_delete_raises_not_found_for_missing_record() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = NetworkElementRepository(session)

        with pytest.raises(NotFoundError, match="Network element 'NE-404' not found."):
            repository.delete("NE-404")
