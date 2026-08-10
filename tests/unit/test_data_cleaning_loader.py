from pathlib import Path

from rkaa.infrastructure.config.data_cleaning_loader import load_data_cleaning_config


def test_default_data_cleaning_config_has_iqr_on_and_z_score_off() -> None:
    path = Path(__file__).resolve().parents[2] / "configs" / "data_cleaning.yaml"

    config = load_data_cleaning_config(path)

    assert config.statistical_outlier.iqr.enabled is True
    assert config.statistical_outlier.z_score.enabled is False
    assert config.restart.enabled is False
