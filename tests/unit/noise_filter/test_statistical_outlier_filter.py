import pandas as pd

from rkaa.domain.noise_filter.models import IQRConfig, StatisticalOutlierConfig, ZScoreConfig
from rkaa.domain.noise_filter.statistical_outlier_filter import StatisticalOutlierFilter


def test_iqr_excludes_outlier_when_group_has_enough_samples() -> None:
    values = [float(value) for value in range(1, 25)] + [100.0]
    df = pd.DataFrame(
        {
            "ne_id": ["NE_A"] * len(values),
            "kpi_name": ["TRAFFIC"] * len(values),
            "value": values,
        }
    )
    config = StatisticalOutlierConfig(
        enabled=True,
        iqr=IQRConfig(enabled=True, multiplier=1.5, min_samples=24),
        z_score=ZScoreConfig(enabled=False),
    )

    result = StatisticalOutlierFilter(config).apply(df)

    assert result.excluded_df["value"].tolist() == [100.0]
    assert result.excluded_df.iloc[0]["filter_reason"] == "IQR_OUTLIER"


def test_iqr_keeps_group_when_samples_are_insufficient() -> None:
    df = pd.DataFrame(
        {
            "ne_id": ["NE_A"] * 5,
            "kpi_name": ["ENDC_SSR"] * 5,
            "value": [99.0, 99.1, 99.2, 99.3, 10.0],
        }
    )
    config = StatisticalOutlierConfig(
        iqr=IQRConfig(enabled=True, min_samples=24),
        z_score=ZScoreConfig(enabled=False),
    )

    result = StatisticalOutlierFilter(config).apply(df)

    assert result.excluded_df.empty
    assert len(result.cleaned_df) == 5
    assert result.summary["iqr_groups_skipped_insufficient"] == 1


def test_z_score_can_be_enabled_independently() -> None:
    values = [0.0] * 20 + [10.0]
    df = pd.DataFrame(
        {
            "ne_id": ["NE_A"] * len(values),
            "kpi_name": ["COUNTER"] * len(values),
            "value": values,
        }
    )
    config = StatisticalOutlierConfig(
        iqr=IQRConfig(enabled=False),
        z_score=ZScoreConfig(enabled=True, threshold=3.0, min_samples=10),
    )

    result = StatisticalOutlierFilter(config).apply(df)

    assert result.excluded_df["value"].tolist() == [10.0]
    assert result.excluded_df.iloc[0]["filter_reason"] == "Z_SCORE_OUTLIER"
