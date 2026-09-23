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

    ingest = sub.add_parser(
        "ingest-zero-variance",
        help="Persist pending FR-302 zero-variance observations into KB history",
    )
    ingest.add_argument("--store", default="tmp/demo/knowledge_base.json")
    ingest.add_argument("--comparison", action="append", required=True)

    show = sub.add_parser("show", help="Show latest KB entry and history")
    show.add_argument("--store", default="tmp/demo/knowledge_base.json")
    show.add_argument("--kpi", required=True)

    export = sub.add_parser("export", help="Export latest approved KB entries to JSON")
    export.add_argument("--store", default="tmp/demo/knowledge_base.json")
    export.add_argument("--output", default="tmp/demo/knowledge_base_latest.json")

    args = parser.parse_args()
    store = KnowledgeStore(_resolve(args.store))

    if args.command == "seed-srs":
        imported = store.import_file(_resolve(args.seed))
        print(f"FR-501 SRS seed imported: {len(imported)} records")
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
            "latest_approved": store.latest(args.kpi, approved_only=True),
            "latest_any": store.latest_any(args.kpi),
            "history": store.history(args.kpi),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    output = _resolve(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(store.list_latest(approved_only=True), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("Export:", output)


if __name__ == "__main__":
    main()
