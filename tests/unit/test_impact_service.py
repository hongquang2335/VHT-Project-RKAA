from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rkaa.core.exceptions import AppError, NotFoundError
from rkaa.domain.impact_service import (
    create_impact_event,
    update_impact_event,
    update_impact_event_status,
)
from rkaa.infrastructure.data_store.base import Base
from rkaa.infrastructure.data_store.models.impact_event import ImpactEvent
from rkaa.infrastructure.data_store.models.network_element import NetworkElement
from rkaa.infrastructure.data_store.repositories.impact_event import ImpactEventRepository
from rkaa.infrastructure.data_store.repositories.network_element import (
    NetworkElementRepository,
)


def _make_network_element(ne_id: str = "NE-001") -> NetworkElement:
    return NetworkElement(
        ne_id=ne_id,
        ne_name=f"Node {ne_id}",
        vendor="VendorX",
        technology="LTE",
        region="HCM",
        site_id=f"SITE-{ne_id}",
        metadata_json={"source": "test"},
    )


def _make_impact_event(ne_id: str = "NE-001", *, status: str = "draft") -> ImpactEvent:
    return ImpactEvent(
        ne_id=ne_id,
        t1=datetime(2026, 7, 8, 0, 0, tzinfo=UTC),
        t2=datetime(2026, 7, 8, 0, 30, tzinfo=UTC),
        impact_type="capacity_degradation",
        description="Detected impact",
        operator="ops",
        source="manual",
        status=status,
    )


def test_create_impact_event_requires_existing_network_element() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        with pytest.raises(NotFoundError, match="Network element 'NE-404' not found."):
            create_impact_event(
                network_elements=NetworkElementRepository(session),
                impacts=ImpactEventRepository(session),
                ne_id="NE-404",
                t1=datetime(2026, 7, 8, 0, 0, tzinfo=UTC),
                t2=None,
                impact_type="capacity_degradation",
                description="Impact on missing NE",
                operator="ops",
                source="manual",
            )


def test_create_impact_event_allows_null_t2_for_ongoing_event() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        network_elements = NetworkElementRepository(session)
        impacts = ImpactEventRepository(session)
        network_elements.create(_make_network_element())
        session.flush()

        created = create_impact_event(
            network_elements=network_elements,
            impacts=impacts,
            ne_id="NE-001",
            t1=datetime(2026, 7, 8, 0, 0, tzinfo=UTC),
            t2=None,
            impact_type="capacity_degradation",
            description="Ongoing impact",
            operator="ops",
            source="manual",
        )
        session.commit()

        loaded = impacts.get_by_id(created.id)

    assert loaded.t2 is None
    assert loaded.status == "draft"


def test_update_impact_event_status_allows_valid_transition() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        network_elements = NetworkElementRepository(session)
        impacts = ImpactEventRepository(session)
        network_elements.create(_make_network_element())
        session.flush()
        created = impacts.create(_make_impact_event())
        session.commit()

        updated = update_impact_event_status(
            impacts=impacts,
            event_id=created.id,
            status="confirmed",
        )
        session.commit()

        loaded = impacts.get_by_id(updated.id)

    assert loaded.status == "confirmed"


def test_update_impact_event_status_rejects_invalid_transition() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        network_elements = NetworkElementRepository(session)
        impacts = ImpactEventRepository(session)
        network_elements.create(_make_network_element())
        session.flush()
        created = impacts.create(_make_impact_event(status="draft"))
        session.commit()

        with pytest.raises(
            AppError,
            match="Invalid impact status transition from 'draft' to 'analyzed'.",
        ):
            update_impact_event_status(
                impacts=impacts,
                event_id=created.id,
                status="analyzed",
            )


def test_update_impact_event_revalidates_network_element_when_ne_changes() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        network_elements = NetworkElementRepository(session)
        impacts = ImpactEventRepository(session)
        network_elements.create(_make_network_element("NE-001"))
        network_elements.create(_make_network_element("NE-002"))
        session.flush()
        created = impacts.create(_make_impact_event("NE-001"))
        session.commit()

        updated = update_impact_event(
            network_elements=network_elements,
            impacts=impacts,
            event_id=created.id,
            ne_id="NE-002",
            t1=datetime(2026, 7, 8, 1, 0, tzinfo=UTC),
            t2=datetime(2026, 7, 8, 1, 45, tzinfo=UTC),
            description="Moved impact scope",
        )
        session.commit()

        loaded = impacts.get_by_id(updated.id)

    assert loaded.ne_id == "NE-002"
    assert loaded.description == "Moved impact scope"
    assert loaded.t2.replace(tzinfo=UTC) == datetime(2026, 7, 8, 1, 45, tzinfo=UTC)


def test_update_impact_event_supports_clearing_t2_to_null() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        network_elements = NetworkElementRepository(session)
        impacts = ImpactEventRepository(session)
        network_elements.create(_make_network_element())
        session.flush()
        created = impacts.create(_make_impact_event())
        session.commit()

        updated = update_impact_event(
            network_elements=network_elements,
            impacts=impacts,
            event_id=created.id,
            t2=None,
            update_t2=True,
        )
        session.commit()

        loaded = impacts.get_by_id(updated.id)

    assert loaded.t2 is None
