from __future__ import annotations

from pathlib import Path

import pytest

from rkaa.domain.data_collector.csv_parser import CSVParseError, parse_kpi_csv

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def test_parse_kpi_csv_returns_valid_rows_and_skips_blank_lines() -> None:
    rows = parse_kpi_csv(FIXTURES_DIR / "kpi_valid.csv")

    assert len(rows) == 2
    assert rows[0].ne_id == "NE-001"
    assert rows[0].kpi_name == "erab_success_rate"
    assert rows[0].value == 98.7
    assert rows[1].kpi_name == "rrc_success_rate"


def test_parse_kpi_csv_rejects_missing_required_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "missing-column.csv"
    csv_path.write_text(
        "\n".join(
            [
                "timestamp,period_end,ne_id,kpi_name,value,unit",
                "2026-07-08T00:00:00+07:00,2026-07-08T00:15:00+07:00,NE-001,erab_success_rate,98.7,percent",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(CSVParseError, match="Missing required CSV columns: quality_flag"):
        parse_kpi_csv(csv_path)


def test_parse_kpi_csv_rejects_invalid_timestamp() -> None:
    with pytest.raises(CSVParseError, match=r"Invalid CSV row at line 2"):
        parse_kpi_csv(FIXTURES_DIR / "kpi_invalid.csv")


def test_parse_kpi_csv_rejects_invalid_value(tmp_path: Path) -> None:
    csv_path = tmp_path / "invalid-value.csv"
    csv_path.write_text(
        "\n".join(
            [
                "timestamp,period_end,ne_id,kpi_name,value,unit,quality_flag",
                "2026-07-08T00:00:00+07:00,2026-07-08T00:15:00+07:00,NE-001,erab_success_rate,abc,percent,good",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(CSVParseError, match=r"Invalid CSV row at line 2"):
        parse_kpi_csv(csv_path)


def test_parse_kpi_csv_rejects_invalid_encoding(tmp_path: Path) -> None:
    csv_path = tmp_path / "invalid-encoding.csv"
    csv_path.write_bytes(b"\xff\xfe\x00\x00")

    with pytest.raises(CSVParseError, match="Unable to decode CSV file"):
        parse_kpi_csv(csv_path)
