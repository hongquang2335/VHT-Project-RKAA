from pathlib import Path

from rkaa.infrastructure.config.station_list_loader import load_station_ids_from_yaml


def test_load_station_ids_from_yaml(tmp_path: Path) -> None:
    path = tmp_path / "stations.yaml"
    path.write_text(
        "stations:\n  - gHM00001\n  - gHM00072\n  - gHM00001\n",
        encoding="utf-8",
    )

    assert load_station_ids_from_yaml(path) == ["gHM00001", "gHM00072"]
