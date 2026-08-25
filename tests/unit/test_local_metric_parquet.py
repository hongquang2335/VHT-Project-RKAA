from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("duckdb")

from rkaa.infrastructure.data_store.local_metric_parquet import LocalMetricParquetStore


def test_local_metric_parquet_store_writes_and_filters(tmp_path: Path) -> None:
    store = LocalMetricParquetStore(tmp_path / "history")
    df = pd.DataFrame(
        {
            "timestamp": ["2026-08-01T00:00:00", "2026-08-01T00:05:00"],
            "period_end": ["2026-08-01T00:05:00", "2026-08-01T00:10:00"],
            "ne_id": ["gHM00001", "gHM00001"],
            "cell_id": ["CELL_A", "CELL_A"],
            "kpi_name": ["KPI_A", "COUNTER_A"],
            "value": [99.0, 10.0],
            "unit": ["%", ""],
            "quality_flag": ["GOOD", "GOOD"],
            "is_counter": [False, True],
        }
    )
    store.write_chunk(
        df,
        start_time=pd.Timestamp("2026-08-01 00:00:00"),
        end_time=pd.Timestamp("2026-08-01 01:00:00"),
    )

    result, count = store.query(
        ne_ids=["gHM00001"],
        metric_kind="kpi",
        start_time="2026-08-01 00:00:00",
        end_time="2026-08-01 01:00:00",
    )

    assert count == 1
    assert result["kpi_name"].tolist() == ["KPI_A"]
    assert result["is_counter"].tolist() == [False]
