import pandas as pd

from rkaa.domain.data_collector.minio_kpi_normalizer import MinioKPINormalizer


def test_two_wide_rows_create_fourteen_long_rows() -> None:
    wide_df = pd.DataFrame({
        "datetime": [
            pd.Timestamp("2026-07-01 00:00:00"),
            pd.Timestamp("2026-07-01 00:15:00"),
        ],
        "cellname": ["CELL_A", "CELL_A"],
        "ENDC SSR VTNET (%)": [99.0, 98.0],
        "ENDC CDR VTNET (%)": [1.0, 2.0],
        "NR RASR VTNET (%)": [95.0, 94.0],
        "PSCell Change Intra-SgNB SR VTNET (%)": [99.0, 98.0],
        "PSCell Change Inter-SgNB SR VTNET (%)": [97.0, 96.0],
        "Max RRC Connected NR ENDC User (UE)": [10, 12],
        "NSA PS Traffic (GBytes)": [20.5, 21.5],
    })

    result = MinioKPINormalizer().normalize(wide_df)

    assert result.shape == (14, 7)
    assert set(result["ne_id"]) == {"CELL_A"}
