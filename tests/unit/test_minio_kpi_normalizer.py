import pandas as pd

from rkaa.domain.data_collector.minio_kpi_normalizer import (
    KPIMappingItem,
    MinioKPINormalizer,
)


def _mapping() -> list[KPIMappingItem]:
    return [
        KPIMappingItem(
            source_column="ENDC SSR VTNET IniAtt (%)",
            canonical_name="ENDC SSR VTNET IniAtt (%)",
            unit="%",
            direction_preference="higher_is_better",
            is_counter=False,
        ),
        KPIMappingItem(
            source_column="pm.SgNB.X2SgNBReconfSuccIniAtt",
            canonical_name="pm.SgNB.X2SgNBReconfSuccIniAtt",
            unit="",
            direction_preference="informational",
            is_counter=True,
        ),
    ]


def test_normalizer_keeps_ne_and_cell_as_separate_identifiers() -> None:
    wide_df = pd.DataFrame({
        "datetime": [pd.Timestamp("2026-07-01 00:00:00")],
        "ne": ["gHM00001"],
        "cellname": ["gHM00001_30"],
        "ENDC SSR VTNET IniAtt (%)": [99.82],
        "pm.SgNB.X2SgNBReconfSuccIniAtt": [124],
    })

    result = MinioKPINormalizer(kpi_mapping=_mapping()).normalize(wide_df)

    assert result.shape == (2, 9)
    assert set(result["ne_id"]) == {"gHM00001"}
    assert set(result["cell_id"]) == {"gHM00001_30"}
    assert result["kpi_name"].tolist() == [
        "ENDC SSR VTNET IniAtt (%)",
        "pm.SgNB.X2SgNBReconfSuccIniAtt",
    ]
    assert result["is_counter"].tolist() == [False, True]
    assert result["period_end"].tolist() == [
        "2026-07-01T00:05:00",
        "2026-07-01T00:05:00",
    ]


def test_normalizer_preserves_null_record_for_fr201() -> None:
    wide_df = pd.DataFrame({
        "datetime": [pd.Timestamp("2026-07-01 00:00:00")],
        "ne": ["gHM00001"],
        "cellname": ["CELL_A"],
        "ENDC SSR VTNET IniAtt (%)": [None],
    })

    result = MinioKPINormalizer(kpi_mapping=_mapping()).normalize(wide_df)

    row = result[result["kpi_name"] == "ENDC SSR VTNET IniAtt (%)"].iloc[0]
    assert row["ne_id"] == "gHM00001"
    assert row["cell_id"] == "CELL_A"
    assert pd.isna(row["value"])
    assert row["quality_flag"] == "MISSING"
    assert bool(row["is_counter"]) is False
