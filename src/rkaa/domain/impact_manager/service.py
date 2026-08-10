"""Dịch vụ nghiệp vụ triển khai các thao tác của FR-103."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from rkaa.domain.impact_manager.models import (
    CreateImpactRequest,
    ImpactEvent,
    ImpactSource,
    ImpactStatus,
    UpdateImpactRequest,
)
from rkaa.domain.impact_manager.repository import ImpactRepository
from rkaa.domain.impact_manager.validators import (
    normalize_optional_text,
    parse_input_datetime,
    parse_optional_end_time,
    require_non_empty,
    validate_impact_type,
    validate_time_window,
)


class ImpactManagerService:
    """Điều phối kiểm tra nghiệp vụ và thao tác lưu trữ Impact Event."""

    def __init__(
        self,
        repository: ImpactRepository,
        *,
        allowed_impact_types: set[str],
        input_timezone: str = "Asia/Ho_Chi_Minh",
    ) -> None:
        if not allowed_impact_types:
            raise ValueError("allowed_impact_types không được rỗng")

        self.repository = repository
        self.allowed_impact_types = {item.upper() for item in allowed_impact_types}
        self.input_timezone = input_timezone

    def create_impact(self, request: CreateImpactRequest) -> ImpactEvent:
        """Kiểm tra, chuẩn hóa và lưu Impact Event được nhập thủ công."""

        ne_id = require_non_empty(request.ne_id, "ne_id")
        cell_id = normalize_optional_text(request.cell_id)
        description = require_non_empty(request.description, "description")
        operator = require_non_empty(request.operator, "operator")
        impact_type = validate_impact_type(
            request.impact_type,
            self.allowed_impact_types,
        )

        t1_utc = parse_input_datetime(
            request.t1,
            input_timezone=self.input_timezone,
        )
        t2_utc = parse_optional_end_time(
            request.t2,
            input_timezone=self.input_timezone,
        )
        validate_time_window(t1_utc, t2_utc)

        now_utc = datetime.now(timezone.utc)
        event = ImpactEvent(
            impact_id=str(uuid4()),
            ne_id=ne_id,
            cell_id=cell_id,
            t1_utc=t1_utc,
            t2_utc=t2_utc,
            impact_type=impact_type,
            description=description,
            operator=operator,
            source=ImpactSource.MANUAL,
            status=(
                ImpactStatus.ONGOING
                if t2_utc is None
                else ImpactStatus.CLOSED
            ),
            created_at_utc=now_utc,
            updated_at_utc=now_utc,
            deleted_at_utc=None,
        )
        return self.repository.create(event)

    def get_impact(
        self,
        impact_id: str,
        *,
        include_deleted: bool = False,
    ) -> ImpactEvent:
        """Trả về Impact Event hoặc phát sinh ``LookupError`` nếu không có."""

        normalized_id = require_non_empty(impact_id, "impact_id")
        event = self.repository.get_by_id(
            normalized_id,
            include_deleted=include_deleted,
        )
        if event is None:
            raise LookupError(f"Không tìm thấy impact_id={normalized_id}")
        return event

    def list_impacts(
        self,
        *,
        ne_id: str | None = None,
        cell_id: str | None = None,
        status: ImpactStatus | str | None = None,
        include_deleted: bool = False,
    ) -> list[ImpactEvent]:
        """Liệt kê Impact Event với các bộ lọc tùy chọn."""

        normalized_status: ImpactStatus | None
        if status is None:
            normalized_status = None
        elif isinstance(status, ImpactStatus):
            normalized_status = status
        else:
            try:
                normalized_status = ImpactStatus(status.strip().upper())
            except ValueError as exc:
                raise ValueError(f"Trạng thái không hợp lệ: {status!r}") from exc

        return self.repository.list_events(
            ne_id=normalize_optional_text(ne_id),
            cell_id=normalize_optional_text(cell_id),
            status=normalized_status,
            include_deleted=include_deleted,
        )

    def update_impact(
        self,
        impact_id: str,
        request: UpdateImpactRequest,
    ) -> ImpactEvent:
        """Cập nhật một phần event đang tồn tại và chưa bị xóa."""

        if not request.has_changes():
            raise ValueError("Cần cung cấp ít nhất một trường để cập nhật")
        if request.clear_cell and request.cell_id is not None:
            raise ValueError("Không dùng đồng thời cell_id và clear_cell")

        current = self.get_impact(impact_id)
        self._ensure_not_deleted(current)

        ne_id = (
            require_non_empty(request.ne_id, "ne_id")
            if request.ne_id is not None
            else current.ne_id
        )

        if request.clear_cell:
            cell_id = None
        elif request.cell_id is not None:
            cell_id = normalize_optional_text(request.cell_id)
        else:
            cell_id = current.cell_id

        description = (
            require_non_empty(request.description, "description")
            if request.description is not None
            else current.description
        )
        operator = (
            require_non_empty(request.operator, "operator")
            if request.operator is not None
            else current.operator
        )
        impact_type = (
            validate_impact_type(request.impact_type, self.allowed_impact_types)
            if request.impact_type is not None
            else current.impact_type
        )
        t1_utc = (
            parse_input_datetime(request.t1, input_timezone=self.input_timezone)
            if request.t1 is not None
            else current.t1_utc
        )
        t2_utc = (
            parse_optional_end_time(request.t2, input_timezone=self.input_timezone)
            if request.t2 is not None
            else current.t2_utc
        )

        validate_time_window(t1_utc, t2_utc)
        updated = replace(
            current,
            ne_id=ne_id,
            cell_id=cell_id,
            t1_utc=t1_utc,
            t2_utc=t2_utc,
            impact_type=impact_type,
            description=description,
            operator=operator,
            status=(
                ImpactStatus.ONGOING
                if t2_utc is None
                else ImpactStatus.CLOSED
            ),
            updated_at_utc=datetime.now(timezone.utc),
        )
        return self.repository.update(updated)

    def close_impact(self, impact_id: str, t2: str) -> ImpactEvent:
        """Đóng event ``ONGOING`` bằng một thời điểm kết thúc hợp lệ."""

        current = self.get_impact(impact_id)
        self._ensure_not_deleted(current)
        if current.status is not ImpactStatus.ONGOING:
            raise ValueError("Chỉ có thể close Impact Event đang ONGOING")

        t2_utc = parse_input_datetime(t2, input_timezone=self.input_timezone)
        validate_time_window(current.t1_utc, t2_utc)
        updated = replace(
            current,
            t2_utc=t2_utc,
            status=ImpactStatus.CLOSED,
            updated_at_utc=datetime.now(timezone.utc),
        )
        return self.repository.update(updated)

    def delete_impact(self, impact_id: str) -> None:
        """Xóa mềm event nhưng vẫn giữ bản ghi để truy vết."""

        current = self.get_impact(impact_id, include_deleted=True)
        if current.status is ImpactStatus.DELETED:
            raise ValueError("Impact Event đã bị xóa")

        deleted_at_utc = datetime.now(timezone.utc)
        deleted = self.repository.soft_delete(current.impact_id, deleted_at_utc)
        if not deleted:
            raise RuntimeError("Không thể xóa Impact Event")

    @staticmethod
    def _ensure_not_deleted(event: ImpactEvent) -> None:
        if event.status is ImpactStatus.DELETED:
            raise ValueError("Không thể sửa Impact Event đã bị xóa")
