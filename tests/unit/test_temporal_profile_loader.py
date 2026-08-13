from __future__ import annotations

from pathlib import Path

import pytest

from rkaa.infrastructure.config.temporal_profile_loader import load_temporal_profile_config


def test_load_default_temporal_profile_config() -> None:
    config = load_temporal_profile_config(Path("configs/temporal_profile.yaml"))

    assert config.timezone == "UTC"
    assert len(config.windows) == 4


def test_loader_rejects_overlap_or_uncovered_minutes(tmp_path: Path) -> None:
    path = tmp_path / "temporal.yaml"
    path.write_text(
        """
timezone: UTC
profiles:
  BUSY:
    - start: "07:00"
      end: "22:00"
  TRANSITION:
    - start: "06:00"
      end: "08:00"
  OFF_PEAK:
    - start: "22:00"
      end: "06:00"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="không overlap"):
        load_temporal_profile_config(path)
