import pandas as pd

from rkaa.domain.noise_filter.models import (
    CustomRuleConfig,
    ImpactWindowConfig,
    NoiseFilterConfig,
    NullSentinelConfig,
    RangeRule,
    RestartConfig,
    StatisticalOutlierConfig,
)
from rkaa.domain.noise_filter.service import NoiseFilterService


def test_service_returns_cleaned_and_excluded_dataframes() -> None:
    df = pd.DataFrame(
        {
            "timestamp": ["2026-07-01 00:00:00"] * 3,
            "period_end": ["2026-07-01 00:15:00"] * 3,
            "ne_id": ["NE_A"] * 3,
            "cell_id": ["CELL_A"] * 3,
            "kpi_name": ["ENDC_SSR"] * 3,
            "value": [99.0, None, 120.0],
            "unit": ["%"] * 3,
            "quality_flag": ["GOOD", "MISSING", "GOOD"],
        }
    )
    config = NoiseFilterConfig(
        null_sentinel=NullSentinelConfig(enabled=True),
        impact_window=ImpactWindowConfig(enabled=False),
        restart=RestartConfig(enabled=False),
        statistical_outlier=StatisticalOutlierConfig(enabled=False),
        custom_rule=CustomRuleConfig(
            enabled=True,
            rules={"ENDC_SSR": RangeRule(min_value=0, max_value=100)},
        ),
    )

    result = NoiseFilterService(config).filter(df)

    assert result.cleaned_df["value"].tolist() == [99.0]
    assert len(result.excluded_df) == 2
    assert set(result.excluded_df["filter_stage"]) == {"NULL_SENTINEL", "CUSTOM_RULE"}
    assert result.summary["input_records"] == 3
    assert result.summary["excluded_records"] == 2
