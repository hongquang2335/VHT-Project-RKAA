"""Configuration loading for RKAA."""

from __future__ import annotations

import os
from datetime import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "config.yaml"
ENV_PREFIX = "RKAA_"


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    timezone: str
    granularity_minutes: int
    baseline_min_clean_days: int
    day_periods: "DayPeriodSettings"


class TimeRangeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: time
    end: time


class DayPeriodSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    busy: TimeRangeSettings
    off_peak: TimeRangeSettings
    transition: TimeRangeSettings


class DatabaseSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str


class LoggingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: str


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app: AppSettings
    database: DatabaseSettings
    logging: LoggingSettings


class ConfigError(ValueError):
    """Raised when configuration cannot be loaded."""


def _parse_scalar(raw_value: str) -> Any:
    value = raw_value.strip()
    if not value:
        return ""
    if value[:1] == value[-1:] and value.startswith(("'", '"')):
        return value[1:-1]
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        return int(value)
    except ValueError:
        return value


def _parse_yaml(content: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]

    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if indent % 2 != 0:
            raise ConfigError(f"Invalid YAML indentation on line {line_number}.")
        if ":" not in stripped:
            raise ConfigError(f"Invalid YAML entry on line {line_number}.")

        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise ConfigError(f"Invalid YAML structure on line {line_number}.")

        current = stack[-1][1]
        if not value:
            child: dict[str, Any] = {}
            current[key] = child
            stack.append((indent, child))
            continue

        current[key] = _parse_scalar(value)

    return root


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _set_nested_value(target: dict[str, Any], path: list[str], value: Any) -> None:
    current = target
    for part in path[:-1]:
        current = current.setdefault(part, {})
    current[path[-1]] = value


def _environment_overrides() -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for key, value in os.environ.items():
        if not key.startswith(ENV_PREFIX):
            continue
        relative_key = key[len(ENV_PREFIX) :]
        parts = [part.lower() for part in relative_key.split("__") if part]
        if not parts:
            continue
        _set_nested_value(overrides, parts, _parse_scalar(value))
    return overrides


def load_settings(config_path: str | Path | None = None) -> Settings:
    path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH

    if not path.exists():
        raise ConfigError(f"Configuration file not found: {path}")

    try:
        data = _parse_yaml(path.read_text(encoding="utf-8"))
        merged = _deep_merge(data, _environment_overrides())
        return Settings.model_validate(merged)
    except ValidationError as exc:
        raise ConfigError(f"Invalid configuration: {exc}") from exc
