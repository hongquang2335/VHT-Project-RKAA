from pathlib import Path

from rkaa.infrastructure.config.kpi_mapping_loader import load_kpi_mapping


def test_project_mapping_has_8_kpis_and_147_counters() -> None:
    root = Path(__file__).resolve().parents[2]
    mapping = load_kpi_mapping(root / "configs" / "kpi_mapping.yaml")

    kpis = [item for item in mapping if not item.is_counter]
    counters = [item for item in mapping if item.is_counter]

    assert len(kpis) == 8
    assert len(counters) == 147
    assert len(mapping) == 155
    assert all(item.canonical_name == item.source_column for item in mapping)

    kpi_names = {item.source_column for item in kpis}
    assert "ENDC SSR VTNET IniAtt (%)" in kpi_names
    assert "EN-DC CSSR (%)" in kpi_names
    assert "ENDC SSR VTNET (%)" not in kpi_names


def test_counter_is_marked_and_keeps_source_name() -> None:
    root = Path(__file__).resolve().parents[2]
    mapping = load_kpi_mapping(root / "configs" / "kpi_mapping.yaml")

    item = next(
        item
        for item in mapping
        if item.source_column == "pm.SgNB.X2SgNBReconfSuccIniAtt"
    )
    assert item.is_counter is True
    assert item.canonical_name == "pm.SgNB.X2SgNBReconfSuccIniAtt"
