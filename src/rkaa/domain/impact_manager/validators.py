"""Các hàm kiểm tra và chuẩn hóa dữ liệu đầu vào của FR-103."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml


ONGOING_VALUE = "ongoing"


def require_non_empty(value: str, field_name: str) -> str:
    """Loại bỏ khoảng trắng và từ chối chuỗi rỗng."""

    if not isinstance(value, str):
        raise TypeError(f"{field_name} phải là chuỗi")

    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} không được để trống")
    return cleaned


def normalize_optional_text(value: str | None) -> str | None:
    """Chuẩn hóa trường văn bản tùy chọn; chuỗi rỗng được đổi thành ``None``."""

    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def parse_input_datetime(
    value: str,
    *,
    input_timezone: str = "Asia/Ho_Chi_Minh",
) -> datetime:
    """Đọc thời gian đầu vào và chuẩn hóa thành ``datetime`` UTC có timezone.

    Chấp nhận chuỗi dùng khoảng trắng hoặc chữ ``T`` giữa ngày và giờ, có hoặc
    không có UTC offset. Chuỗi không có offset được hiểu theo ``input_timezone``.
    """

    cleaned = require_non_empty(value, "datetime")
    if cleaned.endswith(("Z", "z")):
        cleaned = f"{cleaned[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError as exc:
        raise ValueError(
            "Thời gian không hợp lệ. Dùng dạng YYYY-MM-DD HH:MM:SS, "
            "ISO-8601 có offset, hoặc giá trị ongoing cho t2."
        ) from exc

    if parsed.tzinfo is None:
        try:
            source_timezone = ZoneInfo(input_timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Timezone không hợp lệ: {input_timezone}") from exc
        parsed = parsed.replace(tzinfo=source_timezone)

    return parsed.astimezone(timezone.utc)


def parse_optional_end_time(
    value: str | None,
    *,
    input_timezone: str = "Asia/Ho_Chi_Minh",
) -> datetime | None:
    """Đọc thời điểm kết thúc; ``ongoing`` được biểu diễn bằng ``None``."""

    if value is None:
        return None

    cleaned = require_non_empty(value, "t2")
    if cleaned.casefold() == ONGOING_VALUE:
        return None

    return parse_input_datetime(cleaned, input_timezone=input_timezone)


def validate_time_window(t1_utc: datetime, t2_utc: datetime | None) -> None:
    """Kiểm tra timezone và yêu cầu ``t2 > t1`` khi có thời điểm kết thúc."""

    for field_name, value in (("t1", t1_utc), ("t2", t2_utc)):
        if value is not None and value.tzinfo is None:
            raise ValueError(f"{field_name} phải có timezone")

    if t2_utc is not None and t2_utc <= t1_utc:
        raise ValueError("t2 phải lớn hơn t1")


def validate_impact_type(impact_type: str, allowed_types: set[str]) -> str:
    """Chuẩn hóa và kiểm tra mã loại tác động."""

    normalized = require_non_empty(impact_type, "impact_type").upper()
    if normalized not in allowed_types:
        allowed = ", ".join(sorted(allowed_types))
        raise ValueError(
            f"Loại tác động không hợp lệ: {impact_type!r}. "
            f"Giá trị hợp lệ: {allowed}"
        )
    return normalized


def load_allowed_impact_types(path: str | Path) -> set[str]:
    """Đọc các mã loại tác động trong Phụ lục B của SRS từ file YAML."""

    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file impact type: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    items = raw.get("impact_types")
    if not isinstance(items, list) or not items:
        raise ValueError("impact_types.yaml phải chứa danh sách impact_types không rỗng")

    result: set[str] = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"impact_types[{index}] phải là mapping")
        code = require_non_empty(str(item.get("code", "")), f"impact_types[{index}].code")
        normalized = code.upper()
        if normalized in result:
            raise ValueError(f"Impact type bị trùng: {normalized}")
        result.add(normalized)

    return result
