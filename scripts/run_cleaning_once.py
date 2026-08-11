from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rkaa.domain.event_calendar.service import EventCalendarService
from rkaa.domain.noise_filter.models import ExclusionWindow
from rkaa.domain.noise_filter.service import NoiseFilterService
from rkaa.infrastructure.config.data_cleaning_loader import load_data_cleaning_config
from rkaa.infrastructure.data_store.database import (
    create_sqlite_connection,
    initialize_metadata_schema,
)
from rkaa.infrastructure.data_store.impact_repository import SQLiteImpactRepository


def _resolve_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def _load_exclusion_windows(
    *,
    metadata_db: Path,
    allowed_impact_types: tuple[str, ...],
) -> tuple[list[ExclusionWindow], str]:
    """Đọc Event Calendar FR-202 và chuyển sang window của FR-201.

    Database FR-103 cũ được migrate nhẹ để bổ sung cột FR-202. Không có KPI
    nào được ghi vào SQLite; database này chỉ chứa metadata event.
    """

    if not metadata_db.exists():
        return [], "SKIPPED_METADATA_DB_NOT_FOUND"

    connection = create_sqlite_connection(metadata_db)
    try:
        initialize_metadata_schema(connection)
        repository = SQLiteImpactRepository(connection)
        calendar = EventCalendarService(repository)
        events = calendar.list_baseline_exclusions(
            legacy_excluded_impact_types=set(allowed_impact_types),
        )
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc).lower():
            return [], "SKIPPED_IMPACT_TABLE_NOT_FOUND"
        raise
    finally:
        connection.close()

    windows = [
        ExclusionWindow(
            ne_id=event.ne_id,
            cell_id=event.cell_id,
            t1_utc=event.t1_utc,
            t2_utc=event.t2_utc,
            reason=f"{event.category}:{event.reason}",
            source=f"FR202:{event.event_id}",
        )
        for event in events
    ]
    return windows, f"LOADED_{len(windows)}_WINDOWS"


def _print_summary(summary: dict[str, object], impact_source_status: str) -> None:
    print("FR-201 Cleaning Summary")
    print(f"Input records:    {summary['input_records']}")
    print(f"Cleaned records:  {summary['cleaned_records']}")
    print(f"Excluded records: {summary['excluded_records']}")
    print(f"Impact source:    {impact_source_status}")
    print()
    print("Filter status:")

    filters = summary.get("filters", {})
    if not isinstance(filters, dict):
        return

    for name, raw in filters.items():
        if not isinstance(raw, dict):
            print(f"  {name}: {raw}")
            continue
        status = raw.get("status", "UNKNOWN")
        excluded = raw.get("excluded", 0)
        extras = [
            f"{key}={value}"
            for key, value in raw.items()
            if key not in {"status", "excluded"}
        ]
        suffix = "" if not extras else " | " + ", ".join(extras)
        print(f"  {name}: {status} | excluded={excluded}{suffix}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy FR-201 trên dữ liệu long-format")
    parser.add_argument("--input", default="tmp/minio_kpi_long.csv")
    parser.add_argument("--config", default="configs/data_cleaning.yaml")
    parser.add_argument("--metadata-db", default="tmp/rkaa_metadata.db")
    parser.add_argument("--cleaned-output", default="tmp/fr201/cleaned_kpi.csv")
    parser.add_argument("--excluded-output", default="tmp/fr201/excluded_kpi.csv")
    args = parser.parse_args()

    input_path = _resolve_path(args.input)
    config_path = _resolve_path(args.config)
    metadata_db_path = _resolve_path(args.metadata_db)
    cleaned_output_path = _resolve_path(args.cleaned_output)
    excluded_output_path = _resolve_path(args.excluded_output)

    if not input_path.exists():
        parser.error(f"Không tìm thấy input CSV: {input_path}")
    if not config_path.exists():
        parser.error(f"Không tìm thấy config FR-201: {config_path}")

    config = load_data_cleaning_config(config_path)
    long_df = pd.read_csv(input_path)

    exclusion_windows: list[ExclusionWindow] = []
    impact_source_status = "DISABLED"
    if config.impact_window.enabled:
        exclusion_windows, impact_source_status = _load_exclusion_windows(
            metadata_db=metadata_db_path,
            allowed_impact_types=config.impact_window.excluded_impact_types,
        )

    service = NoiseFilterService(config, exclusion_windows=exclusion_windows)
    result = service.filter(long_df)

    cleaned_output_path.parent.mkdir(parents=True, exist_ok=True)
    excluded_output_path.parent.mkdir(parents=True, exist_ok=True)

    result.cleaned_df.to_csv(cleaned_output_path, index=False, encoding="utf-8-sig")
    result.excluded_df.to_csv(excluded_output_path, index=False, encoding="utf-8-sig")

    print("Cleaned output:", cleaned_output_path)
    print("Excluded output:", excluded_output_path)
    print()
    _print_summary(result.summary, impact_source_status)


if __name__ == "__main__":
    main()
