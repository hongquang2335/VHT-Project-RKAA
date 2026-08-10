"""Các mô hình dữ liệu nghiệp vụ dùng trong FR-103 và FR-202."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ImpactStatus(StrEnum):
    """Trạng thái vòng đời của Impact Event được nhập thủ công."""

    ONGOING = "ONGOING"
    CLOSED = "CLOSED"
    DELETED = "DELETED"


class ImpactSource(StrEnum):
    """Nguồn tạo ra Impact Event."""

    MANUAL = "MANUAL"


class EventCategory(StrEnum):
    """Phân loại sự kiện dùng cho FR-202.

    IMPACT giữ tương thích với Impact Event FR-103 hiện có. MAINTENANCE và
    SPECIAL_EVENT là hai nhóm FR-202 cần quản lý riêng để baseline có thể loại
    dữ liệu trong các khoảng này nhưng metadata vẫn được giữ để tra cứu/chart.
    """

    IMPACT = "IMPACT"
    MAINTENANCE = "MAINTENANCE"
    SPECIAL_EVENT = "SPECIAL_EVENT"


@dataclass(frozen=True, slots=True)
class CreateImpactRequest:
    """Dữ liệu đầu vào thô dùng để tạo Impact Event/Event Calendar entry."""

    ne_id: str
    t1: str
    t2: str
    impact_type: str
    description: str
    operator: str
    cell_id: str | None = None
    event_category: EventCategory | str = EventCategory.IMPACT
    # None cho phép giữ hành vi FR-103 cũ: quyết định exclude theo legacy rule.
    # Với MAINTENANCE/SPECIAL_EVENT, service mặc định chuyển None -> True.
    exclude_from_baseline: bool | None = None


@dataclass(frozen=True, slots=True)
class UpdateImpactRequest:
    """Các trường có thể thay đổi sau khi Impact Event được tạo.

    Giá trị ``None`` nghĩa là không cập nhật trường tương ứng. Để bỏ liên kết
    cell hiện có, đặt ``clear_cell=True``. Để chuyển sự kiện về trạng thái đang
    diễn ra, truyền ``t2='ongoing'``.
    """

    ne_id: str | None = None
    t1: str | None = None
    t2: str | None = None
    impact_type: str | None = None
    description: str | None = None
    operator: str | None = None
    cell_id: str | None = None
    clear_cell: bool = False
    event_category: EventCategory | str | None = None
    exclude_from_baseline: bool | None = None
    # Khi True, cột exclude_from_baseline được đưa về NULL để dùng legacy rule.
    clear_exclude_from_baseline: bool = False

    def has_changes(self) -> bool:
        """Kiểm tra yêu cầu cập nhật có chứa ít nhất một thay đổi hay không."""

        return any(
            value is not None
            for value in (
                self.ne_id,
                self.t1,
                self.t2,
                self.impact_type,
                self.description,
                self.operator,
                self.cell_id,
                self.event_category,
                self.exclude_from_baseline,
            )
        ) or self.clear_cell or self.clear_exclude_from_baseline


@dataclass(frozen=True, slots=True)
class ImpactEvent:
    """Impact Event đã được kiểm tra và chuẩn hóa trước khi lưu."""

    impact_id: str
    ne_id: str
    cell_id: str | None
    t1_utc: datetime
    t2_utc: datetime | None
    impact_type: str
    description: str
    operator: str
    source: ImpactSource
    status: ImpactStatus
    created_at_utc: datetime
    updated_at_utc: datetime
    deleted_at_utc: datetime | None = None
    event_category: EventCategory = EventCategory.IMPACT
    # True: luôn loại khỏi baseline; False: luôn giữ; None: legacy FR-103 rule.
    exclude_from_baseline: bool | None = None
