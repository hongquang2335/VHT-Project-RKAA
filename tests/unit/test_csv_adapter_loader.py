from pathlib import Path

import pandas as pd

from rkaa.infrastructure.config.csv_adapter_loader import (
    apply_derived_metrics,
    load_csv_adapter_config,
    resolve_csv_metric_mapping,
)


def test_demo_config_resolves_confirmed_rasr_alias_and_traffic_sum() -> None:
    root = Path(__file__).resolve().parents[2]
    config = load_csv_adapter_config(root / "configs" / "csv_demo_adapter.yaml")
    resolution = resolve_csv_metric_mapping(
        [
            "Datetime",
            "NE Name",
            "Cellname",
            "ENDC SSR  IniAtt (%)",
            "ENDC CDR  (%)",
            "5G RASR CF (%)",
            "NR DL PS Traffic (MAC) (GBytes)",
            "NR UL PS Traffic (MAC) (GBytes)",
        ],
        config,
    )

    by_name = {item.canonical_name: item for item in resolution.mapping}
    assert (
        by_name["ENDC SSR VTNET IniAtt (%)"].source_column
        == "ENDC SSR  IniAtt (%)"
    )
    assert by_name["ENDC CDR VTNET (%)"].source_column == "ENDC CDR  (%)"
    assert by_name["NR RASR VTNET (%)"].source_column == "5G RASR CF (%)"

    assert len(resolution.derived_metrics) == 1
    traffic = resolution.derived_metrics[0]
    assert traffic.canonical_name == "NSA PS Traffic (GBytes)"
    assert traffic.source_columns == (
        "NR DL PS Traffic (MAC) (GBytes)",
        "NR UL PS Traffic (MAC) (GBytes)",
    )

    wide = pd.DataFrame(
        {
            "NR DL PS Traffic (MAC) (GBytes)": [10.0, None],
            "NR UL PS Traffic (MAC) (GBytes)": [2.5, 1.0],
        }
    )
    derived = apply_derived_metrics(wide, resolution)
    assert derived["NSA PS Traffic (GBytes)"].iloc[0] == 12.5
    assert pd.isna(derived["NSA PS Traffic (GBytes)"].iloc[1])


def test_auto_discovery_classifies_pm_and_hash_as_counter() -> None:
    root = Path(__file__).resolve().parents[2]
    config = load_csv_adapter_config(root / "configs" / "csv_demo_adapter.yaml")
    resolution = resolve_csv_metric_mapping(
        [
            "No",
            "Site",
            "Cell",
            "Datetime",
            "NE Name",
            "Cellname",
            "NEW KPI (%)",
            "NEW COUNT (#)",
            "Pm.New.RawCounter",
        ],
        config,
        enable_auto_discovery=True,
    )
    by_source = {item.source_column: item for item in resolution.mapping}
    assert by_source["NEW KPI (%)"].is_counter is False
    assert by_source["NEW KPI (%)"].unit == "%"
    assert by_source["NEW COUNT (#)"].is_counter is True
    assert by_source["Pm.New.RawCounter"].is_counter is True
