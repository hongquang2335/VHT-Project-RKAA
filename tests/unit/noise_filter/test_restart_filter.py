import pandas as pd

from rkaa.domain.noise_filter.models import RestartConfig
from rkaa.domain.noise_filter.restart_filter import RestartFilter


def _counter_rows(metric_name: str) -> list[dict[str, object]]:
    times = [
        "2026-07-01 00:00:00",
        "2026-07-01 00:15:00",
        "2026-07-01 00:30:00",
        "2026-07-01 00:45:00",
        "2026-07-01 01:00:00",
    ]
    values = [1500.0, 1600.0, 10.0, 100.0, 200.0]
    return [
        {
            "timestamp": timestamp,
            "ne_id": "NE_A",
            "kpi_name": metric_name,
            "value": value,
        }
        for timestamp, value in zip(times, values)
    ]


def test_restart_filter_requires_correlated_confirmed_counter_resets() -> None:
    df = pd.DataFrame(_counter_rows("COUNTER_A") + _counter_rows("COUNTER_B"))
    config = RestartConfig(
        enabled=True,
        eligible_metrics=("COUNTER_A", "COUNTER_B"),
        reset_max_value=100,
        min_previous_value=1000,
        min_drop_ratio=0.9,
        confirmation_points=2,
        concurrent_window_minutes=15,
        min_concurrent_counters=2,
        post_restart_grace_minutes=15,
    )

    result = RestartFilter(config).apply(df)

    assert result.summary["counter_resets"] == 2
    assert result.summary["restart_events"] == 1
    assert result.summary["excluded"] == 4
    assert set(result.excluded_df["filter_reason"]) == {"NE_RESTART_DETECTED"}


def test_restart_filter_skips_when_no_eligible_counter_is_configured() -> None:
    df = pd.DataFrame(_counter_rows("COUNTER_A"))

    result = RestartFilter(RestartConfig(enabled=True, eligible_metrics=())).apply(df)

    assert result.summary["status"] == "SKIPPED_NO_ELIGIBLE_COUNTERS"
    assert result.excluded_df.empty
