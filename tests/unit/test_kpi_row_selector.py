import pandas as pd

from rkaa.domain.data_collector.kpi_row_selector import select_kpi_rows


def test_select_kpi_rows_skips_counter_rows() -> None:
    df = pd.DataFrame(
        {
            "kpi_name": ["EN-DC CSSR (%)", "pm.SgNB.X2SgNBReconfSuccIniAtt"],
            "is_counter": [False, True],
        }
    )

    kpi_df, skipped = select_kpi_rows(df)

    assert skipped == 1
    assert kpi_df["kpi_name"].tolist() == ["EN-DC CSSR (%)"]


def test_select_kpi_rows_keeps_legacy_input_without_flag() -> None:
    df = pd.DataFrame({"kpi_name": ["EN-DC CSSR (%)"]})

    kpi_df, skipped = select_kpi_rows(df)

    assert skipped == 0
    assert kpi_df.equals(df)


def test_split_metric_rows_returns_both_streams() -> None:
    from rkaa.domain.data_collector.kpi_row_selector import split_metric_rows

    df = pd.DataFrame(
        {
            "kpi_name": ["EN-DC CSSR (%)", "pm.SgNB.X2SgNBReconfSuccIniAtt"],
            "is_counter": ["False", "True"],
        }
    )

    kpi_df, counter_df = split_metric_rows(df)

    assert kpi_df["kpi_name"].tolist() == ["EN-DC CSSR (%)"]
    assert counter_df["kpi_name"].tolist() == ["pm.SgNB.X2SgNBReconfSuccIniAtt"]
