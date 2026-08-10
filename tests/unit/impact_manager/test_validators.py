from datetime import timezone

import pytest

from rkaa.domain.impact_manager.validators import (
    load_allowed_impact_types,
    parse_input_datetime,
    parse_optional_end_time,
    require_non_empty,
    validate_impact_type,
    validate_time_window,
)


def test_parse_naive_vietnam_time_to_utc() -> None:
    result = parse_input_datetime(
        "2026-07-15 16:50:00",
        input_timezone="Asia/Ho_Chi_Minh",
    )

    assert result.isoformat() == "2026-07-15T09:50:00+00:00"
    assert result.tzinfo is timezone.utc


def test_parse_explicit_offset_to_utc() -> None:
    result = parse_input_datetime("2026-07-15T16:50:00+07:00")
    assert result.isoformat() == "2026-07-15T09:50:00+00:00"


def test_parse_z_suffix_to_utc() -> None:
    result = parse_input_datetime("2026-07-15T09:50:00Z")
    assert result.isoformat() == "2026-07-15T09:50:00+00:00"


def test_ongoing_returns_none() -> None:
    assert parse_optional_end_time("ONGOING") is None


def test_t2_equal_t1_is_rejected() -> None:
    value = parse_input_datetime("2026-07-15 16:50:00")
    with pytest.raises(ValueError, match="t2 phải lớn hơn t1"):
        validate_time_window(value, value)


def test_t2_before_t1_is_rejected() -> None:
    t1 = parse_input_datetime("2026-07-15 16:50:00")
    t2 = parse_input_datetime("2026-07-15 16:49:59")
    with pytest.raises(ValueError, match="t2 phải lớn hơn t1"):
        validate_time_window(t1, t2)


def test_invalid_impact_type_is_rejected() -> None:
    with pytest.raises(ValueError, match="Loại tác động không hợp lệ"):
        validate_impact_type("UNKNOWN", {"NE_RESTART"})


def test_empty_ne_is_rejected() -> None:
    with pytest.raises(ValueError, match="ne_id không được để trống"):
        require_non_empty("  ", "ne_id")


def test_load_allowed_impact_types(tmp_path) -> None:
    config_path = tmp_path / "impact_types.yaml"
    config_path.write_text(
        "impact_types:\n  - code: NE_RESTART\n  - code: AUDIT\n",
        encoding="utf-8",
    )
    assert load_allowed_impact_types(config_path) == {"NE_RESTART", "AUDIT"}
