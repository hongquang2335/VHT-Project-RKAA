import pytest

from rkaa.domain.data_collector.station_selection import normalize_station_ids


def test_normalize_station_ids_strips_empty_and_duplicates() -> None:
    result = normalize_station_ids([" gHM00001 ", "", "gHM00072", "gHM00001"])
    assert result == ["gHM00001", "gHM00072"]


def test_normalize_station_ids_rejects_non_string() -> None:
    with pytest.raises(TypeError):
        normalize_station_ids(["gHM00001", 123])  # type: ignore[list-item]
