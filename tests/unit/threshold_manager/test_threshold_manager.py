from __future__ import annotations

from pathlib import Path

import pytest

from rkaa.domain.threshold_manager import ThresholdManagerService, ThresholdSeverity
from rkaa.infrastructure.config.kpi_threshold_loader import load_kpi_threshold_policies


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "thresholds.yaml"
    path.write_text(
        """
kpis:
  ENDC_CDR:
    direction_preference: lower_is_better
    increase:
      warning: {type: ABSOLUTE, value: 1.0}
      critical: {type: ABSOLUTE, value: 3.0}
  ENDC_SSR:
    direction_preference: higher_is_better
    decrease:
      warning: {type: PERCENTAGE, value: 2.0}
      critical: {type: PERCENTAGE, value: 5.0}
""".strip(),
        encoding="utf-8",
    )
    return path


def test_threshold_manager_supports_absolute_and_percentage(tmp_path: Path) -> None:
    manager = ThresholdManagerService(load_kpi_threshold_policies(_config(tmp_path)))

    cdr = manager.evaluate("ENDC_CDR", delta_absolute=3.5, delta_percent=20.0)
    ssr = manager.evaluate("ENDC_SSR", delta_absolute=-1.0, delta_percent=-2.5)

    assert cdr.severity is ThresholdSeverity.CRITICAL
    assert cdr.matched_threshold == 3.0
    assert ssr.severity is ThresholdSeverity.WARNING
    assert ssr.matched_threshold == 2.0


def test_loader_rejects_critical_lower_than_warning_with_same_mode(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        """
kpis:
  K1:
    increase:
      warning: {type: ABSOLUTE, value: 3}
      critical: {type: ABSOLUTE, value: 2}
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="critical phải >= warning"):
        load_kpi_threshold_policies(path)
