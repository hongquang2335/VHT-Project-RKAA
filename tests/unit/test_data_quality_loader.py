from pathlib import Path

from rkaa.infrastructure.config.data_quality_loader import load_data_quality_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_load_project_data_quality_config() -> None:
    config = load_data_quality_config(
        PROJECT_ROOT / "configs" / "data_quality.yaml"
    )
    assert config.gap.expected_interval_minutes == 5
    assert config.gap.warning_threshold_minutes == 120
    assert config.range_validation.rules["ENDC SSR VTNET IniAtt (%)"].max_value == 100
    assert config.local_spike.enabled is True
    assert config.local_spike.window_samples == 288
    assert config.local_spike.min_samples == 72
