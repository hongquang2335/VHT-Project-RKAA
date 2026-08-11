import pandas as pd

from rkaa.domain.data_quality.local_spike_detector import LocalSpikeDetector
from rkaa.domain.data_quality.models import LocalSpikeConfig


def test_local_spike_uses_previous_samples_only() -> None:
    timestamps = pd.date_range("2026-08-10", periods=7, freq="15min", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "period_end": timestamps + pd.Timedelta(minutes=15),
            "ne_id": ["gHM00001"] * 7,
            "cell_id": ["CELL_A"] * 7,
            "kpi_name": ["ENDC_SSR"] * 7,
            "value": [98.0, 99.0, 98.5, 99.2, 98.8, 99.1, 50.0],
            "_dq_row_id": list(range(7)),
        }
    )
    detector = LocalSpikeDetector(
        LocalSpikeConfig(
            enabled=True,
            window_samples=6,
            min_samples=4,
            robust_z_threshold=6.0,
        )
    )
    issues = detector.detect(df)
    assert len(issues) == 1
    assert issues[0].issue_type == "LOCAL_SPIKE"
    assert issues[0].row_index == 6
    assert issues[0].cell_id == "CELL_A"
