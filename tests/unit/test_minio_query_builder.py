import pytest

from rkaa.domain.data_collector.minio_query_builder import (
    build_minio_kpi_query,
    quote_identifier,
)


def test_quote_identifier_wraps_column_name() -> None:
    assert quote_identifier("datetime") == '"datetime"'


def test_quote_identifier_rejects_tuple() -> None:
    with pytest.raises(TypeError):
        quote_identifier(("datetime",))  # type: ignore[arg-type]


def test_build_query_contains_cell_filter() -> None:
    query = build_minio_kpi_query(
        bucket="bucket",
        selected_columns=["datetime", "ne", "cellname", "ENDC SSR VTNET (%)"],
        datetime_col="datetime",
        ne_col="ne",
        cellname_col="cellname",
        start_time="2026-07-01 00:00:00",
        end_time="2026-07-02 00:00:00",
        cellname="CELL_A",
        limit=100,
    )
    assert '"cellname" = ?' in query.sql
    assert query.params[-1] == "CELL_A"
    assert "LIMIT 100" in query.sql


def test_build_query_filters_multiple_stations_by_ne_column() -> None:
    query = build_minio_kpi_query(
        bucket="bucket",
        selected_columns=["datetime", "ne", "cellname", "ENDC SSR VTNET (%)"],
        datetime_col="datetime",
        ne_col="ne",
        cellname_col="cellname",
        start_time="2026-07-01 00:00:00",
        end_time="2026-07-02 00:00:00",
        station_ids=["gHM00001", "gHM00072"],
    )

    assert query.sql.count('"ne" = ?') == 2
    assert 'starts_with("cellname"' not in query.sql
    assert query.params == [
        "2026-07-01 00:00:00",
        "2026-07-02 00:00:00",
        "gHM00001",
        "gHM00072",
    ]


def test_build_query_rejects_cell_and_station_list_together() -> None:
    with pytest.raises(ValueError):
        build_minio_kpi_query(
            bucket="bucket",
            selected_columns=["datetime", "ne", "cellname"],
            datetime_col="datetime",
            ne_col="ne",
            cellname_col="cellname",
            start_time="2026-07-01 00:00:00",
            end_time="2026-07-02 00:00:00",
            cellname="CELL_A",
            station_ids=["gHM00001"],
        )
