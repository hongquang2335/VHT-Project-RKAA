from __future__ import annotations

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.models import NetworkElement


def test_network_element_model_creates_expected_columns() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)

    Base.metadata.create_all(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("network_elements")}

    assert columns == {
        "ne_id",
        "ne_name",
        "vendor",
        "technology",
        "region",
        "site_id",
        "metadata",
    }


def test_network_element_accepts_allowed_technology() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            NetworkElement(
                ne_id="NE-001",
                ne_name="Node A",
                vendor="VendorX",
                technology="LTE",
                region="HCM",
                site_id="SITE-01",
                metadata_json={"cluster": "A"},
            )
        )
        session.commit()

    with Session(engine) as session:
        created = session.get(NetworkElement, "NE-001")

    assert created is not None
    assert created.technology == "LTE"
    assert created.metadata_json == {"cluster": "A"}


def test_network_element_rejects_invalid_technology() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            NetworkElement(
                ne_id="NE-002",
                ne_name="Node B",
                vendor="VendorY",
                technology="GSM",
                region="HN",
                site_id="SITE-02",
                metadata_json={},
            )
        )

        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        else:
            raise AssertionError("Expected invalid technology to violate the check constraint.")
