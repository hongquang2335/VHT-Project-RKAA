from pathlib import Path

import pandas as pd

from rkaa.domain.data_collector.csv_kpi_adapter import CSVKPIAdapter


def test_csv_adapter_filters_time_station_and_columns(tmp_path: Path) -> None:
    path = tmp_path / "input.csv"
    pd.DataFrame(
        {
            "Datetime": [
                "13/06/2026 13:00",
                "13/06/2026 14:00",
                "13/06/2026 15:00",
            ],
            "NE Name": ["gA", "gA", "gB"],
            "Cellname": ["C1", "C1", "C2"],
            "KPI A (%)": [99.0, 98.0, 97.0],
            "Unused": [1, 2, 3],
        }
    ).to_csv(path, index=False)

    adapter = CSVKPIAdapter(path, dayfirst=True)
    result = adapter.fetch_kpi_wide_dataframe_for_stations(
        station_ids=["gA"],
        selected_columns=["Datetime", "NE Name", "Cellname", "KPI A (%)"],
        datetime_col="Datetime",
        ne_col="NE Name",
        cellname_col="Cellname",
        start_time="2026-06-13 13:30:00",
        end_time="2026-06-13 15:00:00",
    )

    assert result.shape == (1, 4)
    assert result.iloc[0]["NE Name"] == "gA"
    assert float(result.iloc[0]["KPI A (%)"]) == 98.0
    assert "Unused" not in result.columns
