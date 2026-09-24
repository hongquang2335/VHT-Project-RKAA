from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rkaa.domain.knowledge_base import (  # noqa: E402
    KnowledgeBaseService,
    KnowledgeStore,
    ingest_zero_variance_observations,
)


def _resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def main() -> None:
    parser = argparse.ArgumentParser(description="FR-501 Knowledge Base utility")
    sub = parser.add_subparsers(dest="command", required=True)

    seed = sub.add_parser("seed-srs", help="Import approved KPI definitions from SRS seed")
    seed.add_argument("--store", default="tmp/demo/knowledge_base.json")
    seed.add_argument("--seed", default="configs/knowledge_seed_srs.json")

    import_cmd = sub.add_parser("import", help="Import Knowledge Base records from JSON/CSV")
    import_cmd.add_argument("--store", default="tmp/demo/knowledge_base.json")
    import_cmd.add_argument("--file", required=True)

    ingest = sub.add_parser(
        "ingest-zero-variance",
        help="Persist pending FR-302 zero-variance observations into KB history",
    )
    ingest.add_argument("--store", default="tmp/demo/knowledge_base.json")
    ingest.add_argument("--comparison", action="append", required=True)

    show = sub.add_parser("show", help="Show latest KB entry and full version history")
    show.add_argument("--store", default="tmp/demo/knowledge_base.json")
    show.add_argument("--kpi", required=True)

    search = sub.add_parser("search", help="Search latest effective Knowledge Base entries")
    search.add_argument("--store", default="tmp/demo/knowledge_base.json")
    search.add_argument("--query", default="")

    approve = sub.add_parser("approve", help="Approve one KB version (BR-06)")
    approve.add_argument("--store", default="tmp/demo/knowledge_base.json")
    approve.add_argument("--kpi", required=True)
    approve.add_argument("--version", required=True, type=int)
    approve.add_argument("--approved-by", required=True)
    approve.add_argument("--role", required=True, choices=["Engineer", "Admin"])

    export = sub.add_parser("export", help="Export latest approved KB entries to JSON")
    export.add_argument("--store", default="tmp/demo/knowledge_base.json")
    export.add_argument("--output", default="tmp/demo/knowledge_base_latest.json")

    args = parser.parse_args()
    store = KnowledgeStore(_resolve(args.store))
    service = KnowledgeBaseService(store)

    if args.command == "seed-srs":
        imported = service.import_file(_resolve(args.seed), allow_approved=True)
        print(f"FR-501 SRS seed imported: {len(imported)} records")
        print("Store:", store.path)
        return

    if args.command == "import":
        imported = service.import_file(_resolve(args.file))
        print(f"FR-501 records imported: {len(imported)}")
        print("Store:", store.path)
        return

    if args.command == "ingest-zero-variance":
        created = ingest_zero_variance_observations(
            store,
            [_resolve(value) for value in args.comparison],
        )
        print(f"FR-501 zero-variance knowledge versions created: {len(created)}")
        print("Status: PENDING_ENGINEER_REVIEW")
        print("Store:", store.path)
        return

    if args.command == "show":
        payload = {
            "latest_approved": service.get(args.kpi, approved_only=True),
            "latest_any": service.get(args.kpi, approved_only=False),
            "history": service.history(args.kpi),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if args.command == "search":
        print(json.dumps(service.search(args.query), ensure_ascii=False, indent=2))
        return

    if args.command == "approve":
        record = service.approve(
            args.kpi,
            args.version,
            approved_by=args.approved_by,
            approver_role=args.role,
        )
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return

    output = _resolve(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(service.search("", approved_only=True), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("Export:", output)


if __name__ == "__main__":
    main()
