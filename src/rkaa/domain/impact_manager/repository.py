"""Hợp đồng lưu trữ mà tầng nghiệp vụ FR-103 sử dụng."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from rkaa.domain.impact_manager.models import ImpactEvent, ImpactStatus


@runtime_checkable
class ImpactRepository(Protocol):
    """Giao diện tách tầng nghiệp vụ khỏi công nghệ lưu trữ cụ thể."""

    def create(self, event: ImpactEvent) -> ImpactEvent:
        """Lưu và trả về một Impact Event mới."""
        ...

    def get_by_id(
        self,
        impact_id: str,
        *,
        include_deleted: bool = False,
    ) -> ImpactEvent | None:
        """Lấy event theo UUID; trả về ``None`` khi không tồn tại."""
        ...

    def list_events(
        self,
        *,
        ne_id: str | None = None,
        cell_id: str | None = None,
        status: ImpactStatus | None = None,
        include_deleted: bool = False,
    ) -> list[ImpactEvent]:
        """Liệt kê event với bộ lọc NE, cell và trạng thái tùy chọn."""
        ...

    def update(self, event: ImpactEvent) -> ImpactEvent:
        """Lưu và trả về trạng thái đầy đủ sau khi cập nhật event."""
        ...

    def soft_delete(
        self,
        impact_id: str,
        deleted_at_utc: datetime,
    ) -> bool:
        """Đánh dấu event là ``DELETED`` nhưng không xóa bản ghi vật lý."""
        ...
