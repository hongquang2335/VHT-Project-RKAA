import pandas as pd

from rkaa.domain.noise_filter.custom_rule_filter import CustomRuleFilter
from rkaa.domain.noise_filter.models import CustomRuleConfig, RangeRule


def test_custom_rule_filters_values_outside_domain_range() -> None:
    df = pd.DataFrame(
        {
            "kpi_name": ["ENDC_SSR", "ENDC_SSR", "NSA_PS_TRAFFIC"],
            "value": [99.0, 120.0, -1.0],
        }
    )
    config = CustomRuleConfig(
        enabled=True,
        rules={
            "ENDC_SSR": RangeRule(min_value=0, max_value=100),
            "NSA_PS_TRAFFIC": RangeRule(min_value=0),
        },
    )

    result = CustomRuleFilter(config).apply(df)

    assert len(result.cleaned_df) == 1
    assert set(result.excluded_df["filter_reason"]) == {"ABOVE_MAX", "BELOW_MIN"}
