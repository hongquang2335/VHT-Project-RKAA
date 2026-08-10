from dataclasses import replace
from datetime import datetime, timezone

from rkaa.domain.event_calendar.service import EventCalendarService
from rkaa.domain.impact_manager.models import (
    EventCategory,
    ImpactEvent,
    ImpactSource,
    ImpactStatus,
)


class FakeRepository:
    def __init__(self, events: list[ImpactEvent]) -> None:
        self.events = events

    def list_events(self, **kwargs):
        return [event for event in self.events if event.status is not ImpactStatus.DELETED]


def _event(
    event_id: str,
    *,
    category: EventCategory = EventCategory.IMPACT,
    exclude: bool | None = None,
    impact_type: str = "CONFIGURATION_CHANGE",
) -> ImpactEvent:
    now = datetime(2026, 8, 10, 1, 0, tzinfo=timezone.utc)
    return ImpactEvent(
        impact_id=event_id,
        ne_id="gHM00001",
        cell_id=None,
        t1_utc=now,
        t2_utc=now.replace(hour=2),
        impact_type=impact_type,
        description="event",
        operator="tester",
        source=ImpactSource.MANUAL,
        status=ImpactStatus.CLOSED,
        created_at_utc=now,
        updated_at_utc=now,
        event_category=category,
        exclude_from_baseline=exclude,
    )


def test_explicit_fr202_policy_has_priority() -> None:
    events = [
        _event("a", category=EventCategory.MAINTENANCE, exclude=True),
        _event("b", category=EventCategory.SPECIAL_EVENT, exclude=False),
    ]
    result = EventCalendarService(FakeRepository(events)).list_baseline_exclusions(
        legacy_excluded_impact_types={"CONFIGURATION_CHANGE"}
    )
    assert [item.event_id for item in result] == ["a"]


def test_legacy_event_falls_back_to_impact_type() -> None:
    legacy = _event("legacy", exclude=None, impact_type="CONFIGURATION_CHANGE")
    result = EventCalendarService(FakeRepository([legacy])).list_baseline_exclusions(
        legacy_excluded_impact_types={"CONFIGURATION_CHANGE"}
    )
    assert len(result) == 1
    assert result[0].event_id == "legacy"
