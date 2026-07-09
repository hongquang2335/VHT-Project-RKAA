from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from rkaa.core.config import DayPeriodSettings
from rkaa.domain.baseline_grouping import BaselineGroupKey, group_baseline_samples


@dataclass(frozen=True, slots=True)
class KPIBaselineSample:
    ne_id: str
    kpi_name: str
    start_time: datetime
    value: float


def _day_periods() -> DayPeriodSettings:
    return DayPeriodSettings.model_validate(
        {
            "busy": {"start": "07:00", "end": "10:00"},
            "transition": {"start": "10:00", "end": "17:00"},
            "off_peak": {"start": "17:00", "end": "07:00"},
        }
    )


def test_group_baseline_samples_groups_by_all_prompt_dimensions() -> None:
    records = [
        KPIBaselineSample(
            ne_id="NE-001",
            kpi_name="cssr",
            start_time=datetime(2026, 7, 6, 8, 0, tzinfo=UTC),
            value=99.1,
        ),
        KPIBaselineSample(
            ne_id="NE-001",
            kpi_name="cssr",
            start_time=datetime(2026, 7, 6, 8, 15, tzinfo=UTC),
            value=99.3,
        ),
        KPIBaselineSample(
            ne_id="NE-001",
            kpi_name="cssr",
            start_time=datetime(2026, 7, 11, 8, 0, tzinfo=UTC),
            value=98.4,
        ),
        KPIBaselineSample(
            ne_id="NE-001",
            kpi_name="cssr",
            start_time=datetime(2026, 7, 6, 12, 0, tzinfo=UTC),
            value=97.0,
        ),
        KPIBaselineSample(
            ne_id="NE-002",
            kpi_name="cssr",
            start_time=datetime(2026, 7, 6, 8, 0, tzinfo=UTC),
            value=96.5,
        ),
        KPIBaselineSample(
            ne_id="NE-001",
            kpi_name="cdr",
            start_time=datetime(2026, 7, 6, 8, 0, tzinfo=UTC),
            value=0.4,
        ),
    ]

    result = group_baseline_samples(records, day_periods=_day_periods())

    assert result == {
        BaselineGroupKey(
            ne_id="NE-001",
            kpi_name="cssr",
            day_period="busy",
            week_profile="weekday",
        ): [99.1, 99.3],
        BaselineGroupKey(
            ne_id="NE-001",
            kpi_name="cssr",
            day_period="busy",
            week_profile="weekend",
        ): [98.4],
        BaselineGroupKey(
            ne_id="NE-001",
            kpi_name="cssr",
            day_period="transition",
            week_profile="weekday",
        ): [97.0],
        BaselineGroupKey(
            ne_id="NE-002",
            kpi_name="cssr",
            day_period="busy",
            week_profile="weekday",
        ): [96.5],
        BaselineGroupKey(
            ne_id="NE-001",
            kpi_name="cdr",
            day_period="busy",
            week_profile="weekday",
        ): [0.4],
    }


def test_group_baseline_samples_returns_empty_mapping_for_no_records() -> None:
    assert group_baseline_samples([], day_periods=_day_periods()) == {}


def test_group_baseline_samples_preserves_values_in_input_order_per_group() -> None:
    records = [
        KPIBaselineSample(
            ne_id="NE-001",
            kpi_name="throughput",
            start_time=datetime(2026, 7, 6, 8, 0, tzinfo=UTC),
            value=10.0,
        ),
        KPIBaselineSample(
            ne_id="NE-001",
            kpi_name="throughput",
            start_time=datetime(2026, 7, 6, 8, 15, tzinfo=UTC),
            value=12.0,
        ),
    ]

    result = group_baseline_samples(records, day_periods=_day_periods())

    assert result[
        BaselineGroupKey(
            ne_id="NE-001",
            kpi_name="throughput",
            day_period="busy",
            week_profile="weekday",
        )
    ] == [10.0, 12.0]
