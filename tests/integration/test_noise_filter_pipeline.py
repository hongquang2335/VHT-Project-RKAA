from datetime import datetime, timezone

import pandas as pd

from rkaa.domain.noise_filter.models import ExclusionWindow
from rkaa.domain.noise_filter.service import NoiseFilterService
from rkaa.infrastructure.config.data_cleaning_loader import load_data_cleaning_config


def test_fr201_pipeline_produces_cleaned_and_excluded_outputs(tmp_path) -> None:
    config_path = tmp_path / "cleaning.yaml"
    config_path.write_text(
        """
filters:
  null_sentinel:
    enabled: true
    global_values: [-999]
  impact_window:
    enabled: true
    excluded_impact_types: [SOFTWARE_UPGRADE]
    match_mode: exact
  restart:
    enabled: false
  statistical_outlier:
    enabled: false
  custom_rule:
    enabled: true
    rules:
      ENDC_SSR: {min: 0, max: 100}
""".strip(),
        encoding="utf-8",
    )
    config = load_data_cleaning_config(config_path)
    df = pd.DataFrame(
        {
            "timestamp": [
                "2026-07-01 00:00:00",
                "2026-07-01 00:15:00",
                "2026-07-01 00:30:00",
                "2026-07-01 00:45:00",
            ],
            "period_end": [
                "2026-07-01 00:15:00",
                "2026-07-01 00:30:00",
                "2026-07-01 00:45:00",
                "2026-07-01 01:00:00",
            ],
            "ne_id": ["NE_A"] * 4,
            "kpi_name": ["ENDC_SSR"] * 4,
            "value": [99.0, -999.0, 50.0, 120.0],
            "unit": ["%"] * 4,
            "quality_flag": ["GOOD"] * 4,
        }
    )
    windows = [
        ExclusionWindow(
            ne_id="NE_A",
            t1_utc=datetime(2026, 7, 1, 0, 30, tzinfo=timezone.utc),
            t2_utc=datetime(2026, 7, 1, 0, 45, tzinfo=timezone.utc),
            reason="SOFTWARE_UPGRADE",
            source="TEST",
        )
    ]

    result = NoiseFilterService(config, exclusion_windows=windows).filter(df)

    assert result.cleaned_df["value"].tolist() == [99.0]
    assert set(result.excluded_df["filter_stage"]) == {
        "NULL_SENTINEL",
        "IMPACT_WINDOW",
        "CUSTOM_RULE",
    }
