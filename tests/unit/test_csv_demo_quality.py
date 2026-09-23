import pandas as pd

from rkaa.demo.csv_demo_quality import fast_check_csv_demo
from rkaa.domain.data_quality.models import (
    DataQualityConfig,
    DuplicateConfig,
    GapConfig,
    LocalSpikeConfig,
    NormalizationConfig,
    RangeValidationConfig,
)


def _config() -> DataQualityConfig:
    return DataQualityConfig(
        normalization=NormalizationConfig(enabled=True, assume_naive_timezone="UTC"),
        duplicate=DuplicateConfig(enabled=True),
        gap=GapConfig(enabled=True, expected_interval_minutes=60, warning_threshold_minutes=120),
        range_validation=RangeValidationConfig(enabled=False, rules={}, counter_min_value=0),
        local_spike=LocalSpikeConfig(enabled=False, window_samples=24, min_samples=6, robust_z_threshold=6.0),
    )


def test_demo_quality_hourly_sequence_has_no_false_gap_and_deduplicates_exact() -> None:
    frame = pd.DataFrame(
        {
            "timestamp": ["2026-01-01T00:00:00", "2026-01-01T01:00:00", "2026-01-01T01:00:00", "2026-01-01T03:00:00"],
            "period_end": ["2026-01-01T01:00:00", "2026-01-01T02:00:00", "2026-01-01T02:00:00", "2026-01-01T04:00:00"],
            "ne_id": ["N1"] * 4,
            "cell_id": ["C1"] * 4,
            "kpi_name": ["KPI"] * 4,
            "value": [1.0, 2.0, 2.0, 3.0],
            "unit": ["%"] * 4,
            "quality_flag": ["GOOD"] * 4,
            "is_counter": [False] * 4,
        }
    )

    result = fast_check_csv_demo(frame, _config())

    assert len(result.quality_df) == 3
    counts = result.summary["issues_by_type"]
    assert counts["DUPLICATE_EXACT"] == 1
    assert counts["GAP"] == 1
    gap = result.issues_df[result.issues_df["issue_type"] == "GAP"].iloc[0]
    assert gap["severity"] == "INFO"
