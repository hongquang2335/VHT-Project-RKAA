from pathlib import Path

from rkaa.infrastructure.config.data_quality_loader import load_data_quality_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_demo_hourly_quality_config_matches_adapter_granularity() -> None:
    config = load_data_quality_config(
        PROJECT_ROOT / "configs" / "data_quality_demo_hourly.yaml"
    )

    assert config.gap.expected_interval_minutes == 60
    assert config.gap.warning_threshold_minutes == 120
    assert config.local_spike.window_samples == 24
    assert config.local_spike.min_samples == 6
