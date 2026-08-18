from pathlib import Path

import pandas as pd

from rkaa.domain.data_collector.minio_kpi_normalizer import MinioKPINormalizer
from rkaa.infrastructure.config.kpi_mapping_loader import load_kpi_mapping


def test_two_wide_rows_create_kpi_and_counter_long_rows() -> None:
    root = Path(__file__).resolve().parents[2]
    mapping = load_kpi_mapping(root / "configs" / "kpi_mapping.yaml")
    wide_df = pd.DataFrame({
        "datetime": [
            pd.Timestamp("2026-07-01 00:00:00"),
            pd.Timestamp("2026-07-01 00:15:00"),
        ],
        "ne": ["gHM00001", "gHM00001"],
        "cellname": ["CELL_A", "CELL_A"],
        "ENDC SSR VTNET IniAtt (%)": [99.0, 98.0],
        "EN-DC CSSR (%)": [98.5, 98.4],
        "ENDC CDR VTNET (%)": [1.0, 2.0],
        "NR RASR VTNET (%)": [95.0, 94.0],
        "PSCell Change Intra-SgNB SR VTNET (%)": [99.0, 98.0],
        "PSCell Change Inter-SgNB SR VTNET (%)": [97.0, 96.0],
        "Max RRC Connected NR ENDC User (UE)": [10, 12],
        "NSA PS Traffic (GBytes)": [20.5, 21.5],
        "pm.SgNB.X2SgNBReconfSuccIniAtt": [123, 124],
    })

    result = MinioKPINormalizer(kpi_mapping=mapping).normalize(wide_df)

    assert result.shape == (18, 9)
    assert set(result["ne_id"]) == {"gHM00001"}
    assert set(result["cell_id"]) == {"CELL_A"}
    assert int(result["is_counter"].sum()) == 2
    assert set(result.loc[~result["is_counter"], "kpi_name"]) == {
        "ENDC SSR VTNET IniAtt (%)",
        "EN-DC CSSR (%)",
        "ENDC CDR VTNET (%)",
        "NR RASR VTNET (%)",
        "PSCell Change Intra-SgNB SR VTNET (%)",
        "PSCell Change Inter-SgNB SR VTNET (%)",
        "Max RRC Connected NR ENDC User (UE)",
        "NSA PS Traffic (GBytes)",
    }
