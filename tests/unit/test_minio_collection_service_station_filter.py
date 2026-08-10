from __future__ import annotations

import pandas as pd

from rkaa.domain.data_collector.minio_collection_service import MinioCollectionService
from rkaa.domain.data_collector.minio_kpi_normalizer import MinioKPINormalizer


class FakeAdapter:
    def __init__(self) -> None:
        self.received_station_ids: list[str] | None = None

    def fetch_kpi_wide_dataframe_for_stations(self, **kwargs: object) -> pd.DataFrame:
        self.received_station_ids = kwargs["station_ids"]  # type: ignore[assignment]
        return pd.DataFrame(
            {
                "datetime": [pd.Timestamp("2026-07-01 00:00:00")],
                "cellname": ["gHM00001_30n411"],
                "ENDC SSR VTNET (%)": [99.0],
                "ENDC CDR VTNET (%)": [1.0],
                "NR RASR VTNET (%)": [95.0],
                "PSCell Change Intra-SgNB SR VTNET (%)": [99.0],
                "PSCell Change Inter-SgNB SR VTNET (%)": [97.0],
                "Max RRC Connected NR ENDC User (UE)": [10],
                "NSA PS Traffic (GBytes)": [20.5],
            }
        )


def test_collect_for_stations_passes_normalized_list_to_adapter() -> None:
    adapter = FakeAdapter()
    service = MinioCollectionService(
        adapter=adapter,  # type: ignore[arg-type]
        normalizer=MinioKPINormalizer(),
    )

    result = service.collect_for_stations(
        start_time="2026-07-01 00:00:00",
        end_time="2026-07-02 00:00:00",
        station_ids=[" gHM00001 ", "gHM00001"],
    )

    assert adapter.received_station_ids == ["gHM00001"]
    assert result.shape == (7, 7)
    assert set(result["ne_id"]) == {"gHM00001_30n411"}
