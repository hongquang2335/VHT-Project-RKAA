import pandas as pd

from rkaa.domain.data_collector.minio_kpi_normalizer import MinioKPINormalizer


def test_normalizer_keeps_ne_and_cell_as_separate_identifiers() -> None:
    wide_df = pd.DataFrame({
        "datetime": [pd.Timestamp("2026-07-01 00:00:00")],
        "ne": ["gHM00001"],
        "cellname": ["gHM00001_30"],
        "ENDC SSR VTNET (%)": [99.82],
        "ENDC CDR VTNET (%)": [2.95],
        "NR RASR VTNET (%)": [76.18],
        "PSCell Change Intra-SgNB SR VTNET (%)": [99.62],
        "PSCell Change Inter-SgNB SR VTNET (%)": [93.36],
        "Max RRC Connected NR ENDC User (UE)": [25],
        "NSA PS Traffic (GBytes)": [210.8],
    })

    result = MinioKPINormalizer().normalize(wide_df)

    assert result.shape == (7, 8)
    assert set(result["ne_id"]) == {"gHM00001"}
    assert set(result["cell_id"]) == {"gHM00001_30"}


def test_normalizer_preserves_null_record_for_fr201() -> None:
    wide_df = pd.DataFrame({
        "datetime": [pd.Timestamp("2026-07-01 00:00:00")],
        "ne": ["gHM00001"],
        "cellname": ["CELL_A"],
        "ENDC SSR VTNET (%)": [None],
    })

    result = MinioKPINormalizer().normalize(wide_df)

    row = result[result["kpi_name"] == "ENDC_SSR"].iloc[0]
    assert row["ne_id"] == "gHM00001"
    assert row["cell_id"] == "CELL_A"
    assert pd.isna(row["value"])
    assert row["quality_flag"] == "MISSING"
