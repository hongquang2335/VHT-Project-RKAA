from __future__ import annotations

from pathlib import Path

import pytest

from rkaa.core.config import ConfigError, Settings, load_settings


def _write_config(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_load_yaml_successfully(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        """
app:
  name: "RKAA Test"
  timezone: "UTC"
  granularity_minutes: 30
  baseline_min_clean_days: 14
  day_periods:
    busy:
      start: "07:00"
      end: "10:00"
    transition:
      start: "10:00"
      end: "17:00"
    off_peak:
      start: "17:00"
      end: "07:00"
database:
  url: "sqlite:///./test.db"
logging:
  level: "DEBUG"
""".strip(),
    )

    settings = load_settings(config_path)

    assert isinstance(settings, Settings)
    assert settings.app.name == "RKAA Test"
    assert settings.app.timezone == "UTC"
    assert settings.app.granularity_minutes == 30
    assert settings.app.baseline_min_clean_days == 14
    assert settings.app.day_periods.busy.start.isoformat() == "07:00:00"
    assert settings.app.day_periods.off_peak.end.isoformat() == "07:00:00"
    assert settings.database.url == "sqlite:///./test.db"
    assert settings.logging.level == "DEBUG"


def test_environment_variables_override_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        """
app:
  name: "RKAA Test"
  timezone: "UTC"
  granularity_minutes: 15
  baseline_min_clean_days: 14
  day_periods:
    busy:
      start: "07:00"
      end: "10:00"
    transition:
      start: "10:00"
      end: "17:00"
    off_peak:
      start: "17:00"
      end: "07:00"
database:
  url: "sqlite:///./test.db"
logging:
  level: "INFO"
""".strip(),
    )
    monkeypatch.setenv("RKAA_APP__TIMEZONE", "Asia/Ho_Chi_Minh")
    monkeypatch.setenv("RKAA_APP__GRANULARITY_MINUTES", "60")
    monkeypatch.setenv("RKAA_APP__BASELINE_MIN_CLEAN_DAYS", "21")
    monkeypatch.setenv("RKAA_APP__DAY_PERIODS__BUSY__START", "06:00")

    settings = load_settings(config_path)

    assert settings.app.timezone == "Asia/Ho_Chi_Minh"
    assert settings.app.granularity_minutes == 60
    assert settings.app.baseline_min_clean_days == 21
    assert settings.app.day_periods.busy.start.isoformat() == "06:00:00"


def test_missing_required_field_raises_clear_error(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        """
app:
  name: "RKAA Test"
  timezone: "UTC"
database:
  url: "sqlite:///./test.db"
logging:
  level: "INFO"
""".strip(),
    )

    with pytest.raises(ConfigError, match="Invalid configuration"):
        load_settings(config_path)


def test_invalid_field_type_raises_clear_error(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        """
app:
  name: "RKAA Test"
  timezone: "UTC"
  granularity_minutes: "fifteen"
  baseline_min_clean_days: 14
  day_periods:
    busy:
      start: "07:00"
      end: "10:00"
    transition:
      start: "10:00"
      end: "17:00"
    off_peak:
      start: "17:00"
      end: "07:00"
database:
  url: "sqlite:///./test.db"
logging:
  level: "INFO"
""".strip(),
    )

    with pytest.raises(ConfigError, match="Invalid configuration"):
        load_settings(config_path)
