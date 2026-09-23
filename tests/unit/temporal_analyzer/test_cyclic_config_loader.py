from __future__ import annotations

from pathlib import Path

from rkaa.infrastructure.config.cyclic_analysis_loader import load_cyclic_analysis_config

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_default_cyclic_config_has_requested_periods_and_month_disabled() -> None:
    config = load_cyclic_analysis_config(PROJECT_ROOT / "configs" / "cyclic_analysis.yaml")

    assert config.fr401.current_window_hours == 24
    assert config.fr401.comparison_lags_hours == (72, 144, 288)
    assert config.fr402.previous_week_enabled is True
    assert config.fr402.previous_month_enabled is False
    assert config.fr402.previous_month_window_days == 30
