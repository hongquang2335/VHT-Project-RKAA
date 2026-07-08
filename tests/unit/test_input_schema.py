from __future__ import annotations

import pytest
from pydantic import ValidationError

from rkaa.domain.data_collector.schemas import InputSchemaError, KPIInputRow, validate_kpi_input_row


def _valid_payload() -> dict[str, object]:
    return {
        "timestamp": "2026-07-08T00:00:00+07:00",
        "period_end": "2026-07-08T00:15:00+07:00",
        "ne_id": "NE-001",
        "kpi_name": "erab_success_rate",
        "value": "98.7",
        "unit": "percent",
        "quality_flag": "good",
    }


def test_kpi_input_row_accepts_valid_csv_fields() -> None:
    row = KPIInputRow.model_validate(_valid_payload())

    assert row.timestamp.isoformat() == "2026-07-08T00:00:00+07:00"
    assert row.period_end.isoformat() == "2026-07-08T00:15:00+07:00"
    assert row.ne_id == "NE-001"
    assert row.kpi_name == "erab_success_rate"
    assert row.value == 98.7
    assert row.unit == "percent"
    assert row.quality_flag == "good"


def test_kpi_input_row_requires_timezone() -> None:
    payload = _valid_payload()
    payload["timestamp"] = "2026-07-08T00:00:00"

    with pytest.raises(ValidationError):
        KPIInputRow.model_validate(payload)


def test_kpi_input_row_requires_period_end_after_timestamp() -> None:
    payload = _valid_payload()
    payload["period_end"] = "2026-07-07T23:59:00+07:00"

    with pytest.raises(ValidationError):
        KPIInputRow.model_validate(payload)


def test_kpi_input_row_requires_float_value() -> None:
    payload = _valid_payload()
    payload["value"] = "not-a-number"

    with pytest.raises(ValidationError):
        KPIInputRow.model_validate(payload)


def test_kpi_input_row_rejects_empty_ne_id() -> None:
    payload = _valid_payload()
    payload["ne_id"] = "   "

    with pytest.raises(ValidationError):
        KPIInputRow.model_validate(payload)


def test_kpi_input_row_rejects_empty_kpi_name() -> None:
    payload = _valid_payload()
    payload["kpi_name"] = ""

    with pytest.raises(ValidationError):
        KPIInputRow.model_validate(payload)


def test_validate_kpi_input_row_wraps_pydantic_error() -> None:
    payload = _valid_payload()
    payload["period_end"] = payload["timestamp"]

    with pytest.raises(InputSchemaError):
        validate_kpi_input_row(payload)
