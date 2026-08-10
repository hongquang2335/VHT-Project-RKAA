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


def test_exact_duplicate_is_reported_and_one_copy_is_kept() -> None:
    df = pd.DataFrame(
        {
            "timestamp": ["2026-08-10 00:00:00", "2026-08-10 00:00:00"],
            "ne_id": ["gHM00001", "gHM00001"],
            "kpi_name": ["ENDC_SSR", "ENDC_SSR"],
            "value": [99.0, 99.0],
        }
    )
    result = DataQualityService(_base_config()).check(df)
    assert len(result.quality_df) == 1
    assert "DUPLICATE_EXACT" in set(result.issues_df["issue_type"])


def test_conflicting_duplicate_is_kept_and_flagged() -> None:
    df = pd.DataFrame(
        {
            "timestamp": ["2026-08-10 00:00:00", "2026-08-10 00:00:00"],
            "ne_id": ["gHM00001", "gHM00001"],
            "kpi_name": ["ENDC_SSR", "ENDC_SSR"],
            "value": [99.0, 80.0],
        }
    )
    result = DataQualityService(_base_config()).check(df)
    assert len(result.quality_df) == 2
    assert set(result.issues_df["issue_type"]) == {"DUPLICATE_CONFLICT"}
    assert all("DUPLICATE_CONFLICT" in value for value in result.quality_df["data_quality_flags"])


def test_gap_over_two_hours_is_warning() -> None:
    df = pd.DataFrame(
        {
            "timestamp": ["2026-08-10 00:00:00", "2026-08-10 02:30:00"],
            "ne_id": ["gHM00001", "gHM00001"],
            "kpi_name": ["ENDC_SSR", "ENDC_SSR"],
            "value": [99.0, 98.0],
        }
    )
    result = DataQualityService(_base_config()).check(df)
    gap = result.issues_df[result.issues_df["issue_type"] == "GAP"].iloc[0]
    assert gap["severity"] == "WARNING"
    assert result.summary["gaps_over_2h"] == 1


def test_invalid_range_is_flagged_but_record_is_kept() -> None:
    df = pd.DataFrame(
        {
            "timestamp": ["2026-08-10 00:00:00"],
            "ne_id": ["gHM00001"],
            "kpi_name": ["ENDC_SSR"],
            "value": [120.0],
        }
    )
    result = DataQualityService(_base_config()).check(df)
    assert len(result.quality_df) == 1
    assert "INVALID_RANGE" in result.quality_df.iloc[0]["data_quality_flags"]
