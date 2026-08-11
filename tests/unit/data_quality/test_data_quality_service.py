import pandas as pd

from rkaa.domain.data_quality.models import (
    DataQualityConfig,
    GapConfig,
    LocalSpikeConfig,
    QualityRangeRule,
    RangeValidationConfig,
)
from rkaa.domain.data_quality.service import DataQualityService


def _base_config() -> DataQualityConfig:
    return DataQualityConfig(
        gap=GapConfig(
            enabled=True,
            expected_interval_minutes=15,
            warning_threshold_minutes=120,
        ),
        range_validation=RangeValidationConfig(
            enabled=True,
            rules={"ENDC_SSR": QualityRangeRule(min_value=0, max_value=100)},
        ),
        local_spike=LocalSpikeConfig(enabled=False),
    )


def _df(
    timestamps: list[str],
    values: list[float],
    *,
    cells: list[str] | None = None,
) -> pd.DataFrame:
    cells = cells or ["CELL_A"] * len(timestamps)
    starts = pd.to_datetime(timestamps)
    period_ends = (starts + pd.Timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S").tolist()
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "period_end": period_ends,
            "ne_id": ["gHM00001"] * len(timestamps),
            "cell_id": cells,
            "kpi_name": ["ENDC_SSR"] * len(timestamps),
            "value": values,
        }
    )


def test_exact_duplicate_is_reported_and_one_copy_is_kept() -> None:
    df = _df(
        ["2026-08-10 00:00:00", "2026-08-10 00:00:00"],
        [99.0, 99.0],
    )
    result = DataQualityService(_base_config()).check(df)
    assert len(result.quality_df) == 1
    assert "DUPLICATE_EXACT" in set(result.issues_df["issue_type"])


def test_same_time_same_ne_same_kpi_but_different_cells_are_not_duplicates() -> None:
    df = _df(
        ["2026-08-10 00:00:00", "2026-08-10 00:00:00"],
        [99.0, 99.0],
        cells=["CELL_A", "CELL_B"],
    )
    result = DataQualityService(_base_config()).check(df)
    assert len(result.quality_df) == 2
    assert "DUPLICATE_EXACT" not in set(result.issues_df["issue_type"])


def test_same_timestamp_ne_cell_kpi_but_different_period_end_are_not_duplicates() -> None:
    df = _df(
        ["2026-08-10 00:00:00", "2026-08-10 00:00:00"],
        [99.0, 99.0],
    )
    df.loc[1, "period_end"] = "2026-08-10 00:30:00"

    result = DataQualityService(_base_config()).check(df)

    assert len(result.quality_df) == 2
    assert "DUPLICATE_EXACT" not in set(result.issues_df["issue_type"])


def test_conflicting_duplicate_is_kept_and_flagged() -> None:
    df = _df(
        ["2026-08-10 00:00:00", "2026-08-10 00:00:00"],
        [99.0, 80.0],
    )
    result = DataQualityService(_base_config()).check(df)
    assert len(result.quality_df) == 2
    assert set(result.issues_df["issue_type"]) == {"DUPLICATE_CONFLICT"}
    assert all("DUPLICATE_CONFLICT" in value for value in result.quality_df["data_quality_flags"])


def test_gap_over_two_hours_is_warning() -> None:
    df = _df(
        ["2026-08-10 00:00:00", "2026-08-10 02:30:00"],
        [99.0, 98.0],
    )
    result = DataQualityService(_base_config()).check(df)
    gap = result.issues_df[result.issues_df["issue_type"] == "GAP"].iloc[0]
    assert gap["severity"] == "WARNING"
    assert gap["cell_id"] == "CELL_A"
    assert result.summary["gaps_over_2h"] == 1


def test_different_cells_do_not_create_false_gap_between_each_other() -> None:
    df = _df(
        ["2026-08-10 00:00:00", "2026-08-10 02:30:00"],
        [99.0, 98.0],
        cells=["CELL_A", "CELL_B"],
    )
    result = DataQualityService(_base_config()).check(df)
    assert "GAP" not in set(result.issues_df["issue_type"])


def test_invalid_range_is_flagged_but_record_is_kept() -> None:
    df = _df(["2026-08-10 00:00:00"], [120.0])
    result = DataQualityService(_base_config()).check(df)
    assert len(result.quality_df) == 1
    assert "INVALID_RANGE" in result.quality_df.iloc[0]["data_quality_flags"]
    assert result.issues_df.iloc[0]["cell_id"] == "CELL_A"
