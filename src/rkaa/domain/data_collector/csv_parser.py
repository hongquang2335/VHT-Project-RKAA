"""CSV parser for KPI input files."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from rkaa.domain.data_collector.schemas import InputSchemaError, KPIInputRow, validate_kpi_input_row

REQUIRED_COLUMNS = (
    "timestamp",
    "period_end",
    "ne_id",
    "kpi_name",
    "value",
    "unit",
    "quality_flag",
)


class CSVParseError(ValueError):
    """Raised when a KPI CSV file cannot be parsed into internal rows."""


def _read_csv_text(path: str | Path) -> str:
    file_path = Path(path)
    try:
        return file_path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CSVParseError(f"Unable to decode CSV file '{file_path}'.") from exc


def _validate_columns(fieldnames: list[str] | None) -> None:
    actual_columns = fieldnames or []
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in actual_columns]
    if missing_columns:
        raise CSVParseError(
            "Missing required CSV columns: " + ", ".join(missing_columns),
        )


def _is_empty_row(row: dict[str, str | None]) -> bool:
    return all(value is None or not str(value).strip() for value in row.values())


def _parse_kpi_csv_text(content: str) -> list[KPIInputRow]:
    reader = csv.DictReader(io.StringIO(content))
    _validate_columns(reader.fieldnames)

    parsed_rows: list[KPIInputRow] = []
    for line_number, raw_row in enumerate(reader, start=2):
        if _is_empty_row(raw_row):
            continue

        payload = {column: raw_row.get(column) for column in REQUIRED_COLUMNS}
        try:
            parsed_rows.append(validate_kpi_input_row(payload))
        except InputSchemaError as exc:
            raise CSVParseError(f"Invalid CSV row at line {line_number}: {exc}") from exc

    return parsed_rows


def parse_kpi_csv(path: str | Path) -> list[KPIInputRow]:
    """Parse a KPI CSV file into validated internal rows."""

    return _parse_kpi_csv_text(_read_csv_text(path))


def parse_kpi_csv_bytes(payload: bytes, *, source_name: str = "<upload>") -> list[KPIInputRow]:
    """Parse raw CSV bytes into validated internal rows."""

    try:
        content = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CSVParseError(f"Unable to decode CSV file '{source_name}'.") from exc

    return _parse_kpi_csv_text(content)
