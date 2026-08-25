"""Đọc cấu hình temporal profile FR-401."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from rkaa.domain.temporal_analyzer.models import (
    ProfileWindow,
    TemporalProfile,
    TemporalProfileConfig,
)


def _parse_time(value: Any, field_name: str) -> int:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} phải có dạng HH:MM")
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError(f"{field_name} phải có dạng HH:MM")
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise ValueError(f"{field_name} phải có dạng HH:MM") from exc
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError(f"{field_name} không hợp lệ: {value}")
    return hour * 60 + minute


def _validate_full_day_coverage(windows: tuple[ProfileWindow, ...]) -> None:
    profiles = {window.profile for window in windows}
    required = {
        TemporalProfile.BUSY,
        TemporalProfile.OFF_PEAK,
        TemporalProfile.TRANSITION,
    }
    if profiles != required:
        missing = sorted(profile.value for profile in required.difference(profiles))
        extra = sorted(profile.value for profile in profiles.difference(required))
        raise ValueError(
            "FR-401 cần đúng 3 profile BUSY/OFF_PEAK/TRANSITION; "
            f"missing={missing}, extra={extra}"
        )

    for minute in range(24 * 60):
        matches = [window for window in windows if window.contains(minute)]
        if len(matches) != 1:
            hour, minute_part = divmod(minute, 60)
            raise ValueError(
                "Các cửa sổ FR-401 phải phủ đủ 24 giờ và không overlap; "
                f"lỗi tại {hour:02d}:{minute_part:02d}, matches={len(matches)}"
            )


def load_temporal_profile_config(path: str | Path) -> TemporalProfileConfig:
    config_path = Path(path).expanduser().resolve()
    if not config_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy temporal profile config: {config_path}"
        )
    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError("Root của temporal profile config phải là mapping")

    timezone = payload.get("timezone", "UTC")
    if not isinstance(timezone, str):
        raise ValueError("timezone phải là chuỗi IANA timezone")
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Timezone không hợp lệ: {timezone}") from exc

    profiles_raw = payload.get("profiles")
    if not isinstance(profiles_raw, dict):
        raise ValueError("profiles phải là mapping")

    windows: list[ProfileWindow] = []
    for profile_name, profile_windows in profiles_raw.items():
        try:
            profile = TemporalProfile(str(profile_name).upper())
        except ValueError as exc:
            raise ValueError(f"Temporal profile không hợp lệ: {profile_name}") from exc
        if not isinstance(profile_windows, list) or not profile_windows:
            raise ValueError(f"profiles.{profile_name} phải là list không rỗng")
        for index, item in enumerate(profile_windows):
            if not isinstance(item, dict):
                raise ValueError(f"profiles.{profile_name}[{index}] phải là mapping")
            start = _parse_time(item.get("start"), f"{profile_name}[{index}].start")
            end = _parse_time(item.get("end"), f"{profile_name}[{index}].end")
            if start == end:
                raise ValueError(
                    f"{profile_name}[{index}] start và end không được giống nhau"
                )
            windows.append(
                ProfileWindow(profile=profile, start_minute=start, end_minute=end)
            )

    result = tuple(windows)
    _validate_full_day_coverage(result)
    return TemporalProfileConfig(timezone=timezone, windows=result)
