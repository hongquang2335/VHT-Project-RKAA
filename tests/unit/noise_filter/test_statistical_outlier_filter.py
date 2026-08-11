import pandas as pd

from rkaa.domain.noise_filter.models import IQRConfig, StatisticalOutlierConfig, ZScoreConfig
from rkaa.domain.noise_filter.statistical_outlier_filter import StatisticalOutlierFilter


def _series_df(values: list[float], *, cell_id: str = "CELL_A") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ne_id": ["NE_A"] * len(values),
            "cell_id": [cell_id] * len(values),
            "kpi_name": ["TRAFFIC"] * len(values),
            "value": values,
        }
    )


def test_iqr_excludes_outlier_when_cell_group_has_enough_samples() -> None:
    values = [float(value) for value in range(1, 25)] + [100.0]
    config = StatisticalOutlierConfig(
        enabled=True,
        iqr=IQRConfig(enabled=True, multiplier=1.5, min_samples=24),
        z_score=ZScoreConfig(enabled=False),
    )

    result = StatisticalOutlierFilter(config).apply(_series_df(values))

    assert result.excluded_df["value"].tolist() == [100.0]
    assert result.excluded_df.iloc[0]["filter_reason"] == "IQR_OUTLIER"


def test_iqr_keeps_group_when_samples_are_insufficient() -> None:
    df = _series_df([99.0, 99.1, 99.2, 99.3, 10.0])
    df["kpi_name"] = "ENDC_SSR"
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
    df = _series_df(values)
    df["kpi_name"] = "COUNTER"
    config = StatisticalOutlierConfig(
        iqr=IQRConfig(enabled=False),
        z_score=ZScoreConfig(enabled=True, threshold=3.0, min_samples=10),
    )

    result = StatisticalOutlierFilter(config).apply(df)

    assert result.excluded_df["value"].tolist() == [10.0]
    assert result.excluded_df.iloc[0]["filter_reason"] == "Z_SCORE_OUTLIER"


def test_statistical_groups_do_not_mix_cells_of_same_ne() -> None:
    # Mỗi cell chỉ có 3 mẫu, nên với min_samples=4 cả hai phải skip.
    # Nếu code trộn cell thì 6 mẫu sẽ bị xử lý sai như một distribution chung.
    df = pd.concat(
        [
            _series_df([1.0, 1.0, 100.0], cell_id="CELL_A"),
            _series_df([50.0, 50.0, 50.0], cell_id="CELL_B"),
        ],
        ignore_index=True,
    )
    config = StatisticalOutlierConfig(
        iqr=IQRConfig(enabled=True, min_samples=4),
        z_score=ZScoreConfig(enabled=False),
    )

    result = StatisticalOutlierFilter(config).apply(df)

    assert result.excluded_df.empty
    assert result.summary["iqr_groups_skipped_insufficient"] == 2
