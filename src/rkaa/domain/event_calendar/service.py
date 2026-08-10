"""Dịch vụ lịch sự kiện FR-202."""

from __future__ import annotations

from rkaa.domain.event_calendar.models import BaselineExclusionEvent
from rkaa.domain.impact_manager.models import EventCategory, ImpactEvent
from rkaa.domain.impact_manager.repository import ImpactRepository


class EventCalendarService:
    """Cung cấp event cần loại khỏi baseline nhưng vẫn giữ metadata để tra cứu."""

    def __init__(self, repository: ImpactRepository) -> None:
        self.repository = repository

    @staticmethod
    def _should_exclude(
        event: ImpactEvent,
        *,
        legacy_excluded_impact_types: set[str],
    ) -> bool:
        # Record FR-202 mới có quyết định rõ ràng thì ưu tiên giá trị đó.
        if event.exclude_from_baseline is not None:
            return event.exclude_from_baseline

        # Record FR-103 legacy chưa có policy: giữ hành vi FR-201 cũ theo type.
        return event.impact_type in legacy_excluded_impact_types

    def list_baseline_exclusions(
        self,
        *,
        legacy_excluded_impact_types: set[str] | None = None,
    ) -> list[BaselineExclusionEvent]:
        legacy = {item.upper() for item in (legacy_excluded_impact_types or set())}
        events = self.repository.list_events(include_deleted=False)

        result: list[BaselineExclusionEvent] = []
        for event in events:
            if not self._should_exclude(
                event,
                legacy_excluded_impact_types=legacy,
            ):
                continue
            result.append(
                BaselineExclusionEvent(
                    event_id=event.impact_id,
                    ne_id=event.ne_id,
                    cell_id=event.cell_id,
                    t1_utc=event.t1_utc,
                    t2_utc=event.t2_utc,
                    category=event.event_category.value,
                    reason=event.impact_type,
                    description=event.description,
                )
            )
        return result

    def list_calendar_events(
        self,
        *,
        category: EventCategory | None = None,
    ) -> list[ImpactEvent]:
        """Tra cứu event cho chart/UI sau này, không làm mất dữ liệu event."""

        return self.repository.list_events(
            event_category=category,
            include_deleted=False,
        )
