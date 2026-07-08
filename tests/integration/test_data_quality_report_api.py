from __future__ import annotations

from fastapi.testclient import TestClient

from rkaa.main import app


def test_data_quality_report_api_returns_aggregated_summary() -> None:
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/api/v1/data-quality/report",
        json={
            "records": [
                {
                    "ne_id": "NE-001",
                    "kpi_name": "counter_a",
                    "start_time": "2026-07-07T00:00:00Z",
                    "value": 10.0,
                },
                {
                    "ne_id": "NE-001",
                    "kpi_name": "counter_a",
                    "start_time": "2026-07-07T00:15:00Z",
                    "value": -9999.0,
                },
                {
                    "ne_id": "NE-001",
                    "kpi_name": "counter_a",
                    "start_time": "2026-07-07T00:15:00Z",
                    "value": 25.0,
                },
                {
                    "ne_id": "NE-001",
                    "kpi_name": "counter_a",
                    "start_time": "2026-07-07T00:45:00Z",
                    "value": 3.0,
                },
                {
                    "ne_id": "NE-001",
                    "kpi_name": "counter_a",
                    "start_time": "2026-07-07T01:00:00Z",
                    "value": 1000.0,
                },
            ],
            "kpi_definition": {
                "data_type": "counter",
                "valid_min": 0.0,
                "valid_max": 10000.0,
            },
            "granularity_minutes": 15,
            "iqr_multiplier": 1.0,
            "sentinel_values": [-9999.0],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "completeness": 5 / 6,
        "missing_intervals": 1,
        "duplicate_count": 1,
        "invalid_count": 1,
        "noise_ratio": 4 / 5,
        "counter_reset_count": 1,
    }
