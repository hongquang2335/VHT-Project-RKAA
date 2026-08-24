from pathlib import Path

import pandas as pd

from rkaa.domain.data_quality.service import DataQualityService
from rkaa.infrastructure.config.data_quality_loader import load_data_quality_config


def test_fr203_pipeline_generates_quality_issues_and_summary() -> None:
    root = Path(__file__).resolve().parents[2]
    config = load_data_quality_config(root / "configs" / "data_quality.yaml")
    df = pd.DataFrame(
        {
            "timestamp": [
                "2026-08-10 00:00:00",
                "2026-08-10 00:00:00",
                "2026-08-10 03:00:00",
            ],
            "period_end": [
                "2026-08-10 00:15:00",
                "2026-08-10 00:15:00",
                "2026-08-10 03:15:00",
            ],
            "ne_id": ["gHM00001"] * 3,
            "cell_id": ["CELL_A"] * 3,
            "kpi_name": ["ENDC SSR VTNET IniAtt (%)"] * 3,
            "value": [99.0, 99.0, 120.0],
            "unit": ["%"] * 3,
            "quality_flag": ["GOOD"] * 3,
        }
    )
    result = DataQualityService(config).check(df)
    assert len(result.quality_df) == 2
    assert {"DUPLICATE_EXACT", "GAP", "INVALID_RANGE"}.issubset(
        set(result.issues_df["issue_type"])
    )
    assert result.summary["gaps_over_2h"] == 1
    assert "cell_id" in result.issues_df.columns
    assert "period_end" in result.issues_df.columns
    assert not result.summary_df.empty


def test_fr203_observation_keeps_both_kpi_and_counter() -> None:
    root = Path(__file__).resolve().parents[2]
    config = load_data_quality_config(root / "configs" / "data_quality.yaml")
    df = pd.DataFrame(
        {
            "timestamp": ["2026-08-10 00:00:00", "2026-08-10 00:00:00"],
            "period_end": ["2026-08-10 00:15:00", "2026-08-10 00:15:00"],
            "ne_id": ["gHM00001", "gHM00001"],
            "cell_id": ["CELL_A", "CELL_A"],
            "kpi_name": [
                "ENDC SSR VTNET IniAtt (%)",
                "pm.SgNB.X2SgNBReconfSuccIniAtt",
            ],
            "value": [99.0, -1.0],
            "unit": ["%", "count"],
            "quality_flag": ["GOOD", "GOOD"],
            "is_counter": [False, True],
        }
    )

    result = DataQualityService(config).check(df)

    assert len(result.quality_df) == 2
    assert set(result.quality_df["is_counter"].tolist()) == {False, True}
    counter_row = result.quality_df.loc[result.quality_df["is_counter"]].iloc[0]
    assert "INVALID_RANGE" in counter_row["data_quality_flags"]
