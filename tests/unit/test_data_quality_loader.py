from pathlib import Path

from rkaa.infrastructure.config.data_quality_loader import load_data_quality_config


def test_load_project_data_quality_config() -> None:
    root = Path(__file__).resolve().parents[2]
    config = load_data_quality_config(root / "configs" / "data_quality.yaml")
    assert config.gap.expected_interval_minutes == 15
    assert config.gap.warning_threshold_minutes == 120
    assert config.range_validation.rules["ENDC SSR VTNET IniAtt (%)"].max_value == 100
    assert config.local_spike.enabled is True
