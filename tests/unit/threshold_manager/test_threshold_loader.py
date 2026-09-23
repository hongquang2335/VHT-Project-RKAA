from __future__ import annotations

from pathlib import Path

from rkaa.infrastructure.config.kpi_threshold_loader import load_kpi_threshold_manager

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_default_threshold_yaml_loads_without_forcing_demo_thresholds() -> None:
    manager = load_kpi_threshold_manager(PROJECT_ROOT / "configs" / "kpi_thresholds.yaml")

    rule = manager.get("NR RASR VTNET (%)")
    assert rule is not None
    assert rule.direction_preference == "higher_is_better"
    result = manager.evaluate("NR RASR VTNET (%)", delta_abs=-2.0, delta_percent=-2.1)
    assert result["threshold_configured"] is False
    assert result["threshold_severity"] == "NORMAL"
    assert result["change_assessment"] == "degrading"
