"""CLI nhập và quản lý Impact Event thủ công cho FR-103."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rkaa.domain.impact_manager.models import (  # noqa: E402
    CreateImpactRequest,
    EventCategory,
    ImpactEvent,
    ImpactStatus,
    UpdateImpactRequest,
)
from rkaa.domain.impact_manager.service import ImpactManagerService  # noqa: E402
from rkaa.domain.impact_manager.validators import (  # noqa: E402
    load_allowed_impact_types,
)
from rkaa.infrastructure.data_store.database import (  # noqa: E402
    create_sqlite_connection,
    initialize_metadata_schema,
)
from rkaa.infrastructure.data_store.impact_repository import (  # noqa: E402
    SQLiteImpactRepository,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="FR-103/FR-202: quản lý Impact Event, Maintenance và Special Event",
    )
    parser.add_argument(
        "--database",
        default="tmp/rkaa_metadata.db",
        help="Cơ sở dữ liệu SQLite lưu metadata, mặc định tmp/rkaa_metadata.db",
    )
    parser.add_argument(
        "--impact-types",
        default="configs/impact_types.yaml",
        help="File YAML chứa loại tác động hợp lệ",
    )
    parser.add_argument(
        "--input-timezone",
        default="Asia/Ho_Chi_Minh",
        help="Múi giờ áp dụng cho thời gian đầu vào không có offset",
    )
    parser.add_argument(
        "--display-timezone",
        default="Asia/Ho_Chi_Minh",
        help="Múi giờ dùng khi hiển thị",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Tạo Impact Event")
    create.add_argument("--ne", required=True, dest="ne_id")
    create.add_argument("--cell", default=None, dest="cell_id")
    create.add_argument("--t1", required=True)
    create.add_argument("--t2", required=True, help="Thời gian hoặc ongoing")
    create.add_argument("--type", required=True, dest="impact_type")
    create.add_argument("--description", required=True)
    create.add_argument("--operator", required=True)
    create.add_argument(
        "--category",
        choices=[category.value for category in EventCategory],
        default=EventCategory.IMPACT.value,
        dest="event_category",
        help="FR-202: IMPACT, MAINTENANCE hoặc SPECIAL_EVENT",
    )
    create_policy = create.add_mutually_exclusive_group()
    create_policy.add_argument(
        "--exclude-from-baseline",
        action="store_true",
        dest="exclude_from_baseline",
        default=None,
    )
    create_policy.add_argument(
        "--include-in-baseline",
        action="store_false",
        dest="exclude_from_baseline",
    )

    show = subparsers.add_parser("show", help="Xem một Impact Event")
    show.add_argument("--id", required=True, dest="impact_id")
    show.add_argument("--include-deleted", action="store_true")

    list_command = subparsers.add_parser("list", help="Liệt kê Impact Event")
    list_command.add_argument("--ne", default=None, dest="ne_id")
    list_command.add_argument("--cell", default=None, dest="cell_id")
    list_command.add_argument(
        "--status",
        choices=[status.value for status in ImpactStatus],
        default=None,
    )
    list_command.add_argument(
        "--category",
        choices=[category.value for category in EventCategory],
        default=None,
        dest="event_category",
    )
    list_policy = list_command.add_mutually_exclusive_group()
    list_policy.add_argument(
        "--exclude-from-baseline",
        action="store_true",
        dest="exclude_from_baseline",
        default=None,
    )
    list_policy.add_argument(
        "--include-in-baseline",
        action="store_false",
        dest="exclude_from_baseline",
    )
    list_command.add_argument("--include-deleted", action="store_true")

    update = subparsers.add_parser("update", help="Sửa Impact Event")
    update.add_argument("--id", required=True, dest="impact_id")
    update.add_argument("--ne", default=None, dest="ne_id")
    update.add_argument("--cell", default=None, dest="cell_id")
    update.add_argument("--clear-cell", action="store_true")
    update.add_argument("--t1", default=None)
    update.add_argument("--t2", default=None, help="Thời gian hoặc ongoing")
    update.add_argument("--type", default=None, dest="impact_type")
    update.add_argument("--description", default=None)
    update.add_argument("--operator", default=None)
    update.add_argument(
        "--category",
        choices=[category.value for category in EventCategory],
        default=None,
        dest="event_category",
    )
    update_policy = update.add_mutually_exclusive_group()
    update_policy.add_argument(
        "--exclude-from-baseline",
        action="store_true",
        dest="exclude_from_baseline",
        default=None,
    )
    update_policy.add_argument(
        "--include-in-baseline",
        action="store_false",
        dest="exclude_from_baseline",
    )
    update_policy.add_argument(
        "--legacy-baseline-policy",
        action="store_true",
        dest="clear_exclude_from_baseline",
        help="Đưa policy về legacy: FR-201 quyết định theo impact_type",
    )

    close = subparsers.add_parser("close", help="Đóng event ONGOING")
    close.add_argument("--id", required=True, dest="impact_id")
    close.add_argument("--t2", required=True)

    delete = subparsers.add_parser("delete", help="Xóa mềm Impact Event")
    delete.add_argument("--id", required=True, dest="impact_id")

    return parser


def _resolve_project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def _format_datetime(value: datetime | None, display_timezone: str) -> str:
    if value is None:
        return "ongoing"
    try:
        zone = ZoneInfo(display_timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Timezone hiển thị không hợp lệ: {display_timezone}") from exc
    return value.astimezone(zone).isoformat(sep=" ", timespec="seconds")


def print_event(event: ImpactEvent, display_timezone: str) -> None:
    values = {
        "impact_id": event.impact_id,
        "ne_id": event.ne_id,
        "cell_id": event.cell_id or "-",
        "t1": _format_datetime(event.t1_utc, display_timezone),
        "t2": _format_datetime(event.t2_utc, display_timezone),
        "impact_type": event.impact_type,
        "event_category": event.event_category.value,
        "exclude_from_baseline": (
            "legacy" if event.exclude_from_baseline is None else str(event.exclude_from_baseline)
        ),
        "description": event.description,
        "operator": event.operator,
        "source": event.source.value,
        "status": event.status.value,
        "created_at": _format_datetime(event.created_at_utc, display_timezone),
        "updated_at": _format_datetime(event.updated_at_utc, display_timezone),
        "deleted_at": (
            _format_datetime(event.deleted_at_utc, display_timezone)
            if event.deleted_at_utc is not None
            else "-"
        ),
    }
    width = max(len(key) for key in values)
    for key, value in values.items():
        print(f"{key:<{width}} : {value}")


def print_event_list(events: list[ImpactEvent], display_timezone: str) -> None:
    if not events:
        print("Không có Impact Event phù hợp.")
        return

    header = (
        f"{'impact_id':36}  {'ne_id':14}  {'cell_id':18}  "
        f"{'t1':25}  {'t2':25}  {'status':9}  {'category':13}  impact_type"
    )
    print(header)
    print("-" * len(header))
    for event in events:
        t1 = _format_datetime(event.t1_utc, display_timezone)
        t2 = _format_datetime(event.t2_utc, display_timezone)
        print(
            f"{event.impact_id:36}  {event.ne_id[:14]:14}  "
            f"{(event.cell_id or '-')[:18]:18}  {t1:25}  {t2:25}  "
            f"{event.status.value:9}  {event.event_category.value:13}  {event.impact_type}"
        )


def run_command(
    args: argparse.Namespace,
    service: ImpactManagerService,
) -> None:
    if args.command == "create":
        started = perf_counter()
        event = service.create_impact(
            CreateImpactRequest(
                ne_id=args.ne_id,
                cell_id=args.cell_id,
                t1=args.t1,
                t2=args.t2,
                impact_type=args.impact_type,
                description=args.description,
                operator=args.operator,
                event_category=args.event_category,
                exclude_from_baseline=args.exclude_from_baseline,
            )
        )
        elapsed = perf_counter() - started
        print("Đã tạo Impact Event thành công")
        print_event(event, args.display_timezone)
        print(f"thoi_gian_xu_ly_giay : {elapsed:.6f}")
        if elapsed > 2.0:
            print("CẢNH BÁO: thời gian lưu vượt tiêu chí FR-103 là 2 giây", file=sys.stderr)
        return

    if args.command == "show":
        event = service.get_impact(
            args.impact_id,
            include_deleted=args.include_deleted,
        )
        print_event(event, args.display_timezone)
        return

    if args.command == "list":
        events = service.list_impacts(
            ne_id=args.ne_id,
            cell_id=args.cell_id,
            status=args.status,
            event_category=args.event_category,
            exclude_from_baseline=args.exclude_from_baseline,
            include_deleted=args.include_deleted,
        )
        print_event_list(events, args.display_timezone)
        return

    if args.command == "update":
        event = service.update_impact(
            args.impact_id,
            UpdateImpactRequest(
                ne_id=args.ne_id,
                cell_id=args.cell_id,
                clear_cell=args.clear_cell,
                t1=args.t1,
                t2=args.t2,
                impact_type=args.impact_type,
                description=args.description,
                operator=args.operator,
                event_category=args.event_category,
                exclude_from_baseline=args.exclude_from_baseline,
                clear_exclude_from_baseline=args.clear_exclude_from_baseline,
            ),
        )
        print("Đã cập nhật Impact Event thành công")
        print_event(event, args.display_timezone)
        return

    if args.command == "close":
        event = service.close_impact(args.impact_id, args.t2)
        print("Đã đóng Impact Event thành công")
        print_event(event, args.display_timezone)
        return

    if args.command == "delete":
        service.delete_impact(args.impact_id)
        print(f"Đã xóa mềm Impact Event: {args.impact_id}")
        return

    raise RuntimeError(f"Lệnh chưa được xử lý: {args.command}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    database_path = _resolve_project_path(args.database)
    impact_types_path = _resolve_project_path(args.impact_types)
    connection = None

    try:
        allowed_types = load_allowed_impact_types(impact_types_path)
        connection = create_sqlite_connection(database_path)
        initialize_metadata_schema(connection)
        repository = SQLiteImpactRepository(connection)
        service = ImpactManagerService(
            repository,
            allowed_impact_types=allowed_types,
            input_timezone=args.input_timezone,
        )
        run_command(args, service)
    except (FileNotFoundError, LookupError, TypeError, ValueError, RuntimeError) as exc:
        parser.exit(status=2, message=f"LỖI: {exc}\n")
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    main()
