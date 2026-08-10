"""Các mô hình dữ liệu nghiệp vụ dùng trong FR-103."""

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


@dataclass(frozen=True, slots=True)
class CreateImpactRequest:
    """Dữ liệu đầu vào thô dùng để tạo Impact Event."""

    ne_id: str
    t1: str
    t2: str
    impact_type: str
    description: str
    operator: str
    cell_id: str | None = None


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
            )
        ) or self.clear_cell


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
