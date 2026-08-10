import math

import pandas as pd

from rkaa.domain.noise_filter.models import NullSentinelConfig
from rkaa.domain.noise_filter.null_sentinel_filter import NullSentinelFilter


def test_null_sentinel_filter_excludes_null_inf_and_configured_sentinel() -> None:
    df = pd.DataFrame(
        {
            "timestamp": ["2026-07-01 00:00:00"] * 5,
            "ne_id": ["NE_A"] * 5,
            "kpi_name": ["ENDC_SSR"] * 5,
            "value": [99.0, None, math.inf, -999.0, 98.0],
        }
    )
    rule = NullSentinelFilter(
        NullSentinelConfig(enabled=True, global_values=(-999.0,))
    )

    result = rule.apply(df)

    assert result.cleaned_df["value"].tolist() == [99.0, 98.0]
    assert set(result.excluded_df["filter_reason"]) == {"NULL", "NON_FINITE", "SENTINEL"}
    assert result.summary["excluded"] == 3
