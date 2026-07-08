"""Aggregate data quality checks into a summary report."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from rkaa.domain.noise_filter.counter_reset_detector import detect_counter_resets
from rkaa.domain.noise_filter.duplicate_checker import detect_duplicate_records
from rkaa.domain.noise_filter.gap_detector import detect_time_series_gaps
from rkaa.domain.noise_filter.iqr_outlier_filter import detect_iqr_outliers
from rkaa.domain.noise_filter.null_filter import detect_null_sentinel
from rkaa.domain.noise_filter.range_validator import validate_value_range


@dataclass(frozen=True, slots=True)
class DataQualityKPIDefinition:
    """Minimal KPI definition required for quality checks."""

    data_type: str
    valid_min: float | None = None
    valid_max: float | None = None


@dataclass(frozen=True, slots=True)
class DataQualityRecord:
    """Input record used by the data quality reporting service."""

    ne_id: str
    kpi_name: str
    start_time: datetime
    value: float | None


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    """Summary of data quality indicators for a KPI time series."""

    completeness: float
    missing_intervals: int
    duplicate_count: int
    invalid_count: int
    noise_ratio: float
    counter_reset_count: int

    def to_dict(self) -> dict[str, float | int]:
        return {
            "completeness": self.completeness,
            "missing_intervals": self.missing_intervals,
            "duplicate_count": self.duplicate_count,
            "invalid_count": self.invalid_count,
            "noise_ratio": self.noise_ratio,
            "counter_reset_count": self.counter_reset_count,
        }


def build_data_quality_report(
    records: Iterable[DataQualityRecord],
    *,
    kpi_definition: DataQualityKPIDefinition,
    granularity_minutes: int | None = None,
    iqr_multiplier: float = 1.5,
    sentinel_values: Iterable[object] = (),
) -> DataQualityReport:
    """Run the available quality checkers and summarize their results."""

    record_list = list(records)
    total_records = len(record_list)

    duplicate_results = detect_duplicate_records(record_list)
    duplicate_indices = {result.record_index for result in duplicate_results}

    invalid_indices: set[int] = set()
    valid_numeric_records: list[DataQualityRecord] = []
    valid_numeric_index_map: list[int] = []
    for index, record in enumerate(record_list):
        null_result = detect_null_sentinel(record.value, sentinel_values=sentinel_values)
        if null_result.is_noise:
            invalid_indices.add(index)
            continue

        if record.value is None:
            invalid_indices.add(index)
            continue

        range_result = validate_value_range(record.value, kpi_definition)
        if range_result.is_noise:
            invalid_indices.add(index)
            continue

        valid_numeric_records.append(record)
        valid_numeric_index_map.append(index)

    gap_results = detect_time_series_gaps(record_list, granularity_minutes=granularity_minutes)
    missing_intervals = sum(result.missing_periods for result in gap_results)

    counter_reset_results = detect_counter_resets(valid_numeric_records, kpi_definition)
    counter_reset_indices = {
        valid_numeric_index_map[result.record_index] for result in counter_reset_results
    }

    outlier_results = detect_iqr_outliers(valid_numeric_records, multiplier=iqr_multiplier)
    outlier_indices = {valid_numeric_index_map[result.record_index] for result in outlier_results}

    noisy_indices = invalid_indices | duplicate_indices | counter_reset_indices | outlier_indices
    noise_ratio = len(noisy_indices) / total_records if total_records else 0.0

    expected_records = total_records + missing_intervals
    completeness = total_records / expected_records if expected_records else 0.0

    return DataQualityReport(
        completeness=completeness,
        missing_intervals=missing_intervals,
        duplicate_count=len(duplicate_results),
        invalid_count=len(invalid_indices),
        noise_ratio=noise_ratio,
        counter_reset_count=len(counter_reset_results),
    )
