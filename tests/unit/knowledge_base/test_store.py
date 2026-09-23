from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from rkaa.domain.knowledge_base import (
    KnowledgeEntry,
    KnowledgeStore,
    ingest_zero_variance_observations,
)


def test_fr501_keeps_versions_and_latest_approved(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path / "kb.json")
    v1 = store.upsert(
        KnowledgeEntry(
            kpi_name="KPI_A",
            unit="%",
            direction_preference="higher_is_better",
            source="SRS",
            approved=True,
        )
    )
    v2 = store.upsert(
        KnowledgeEntry(
            kpi_name="KPI_A",
            unit="%",
            direction_preference="higher_is_better",
            operational_notes=[{"note": "runtime observation"}],
            source="runtime",
            approved=False,
        )
    )

    assert v1["version"] == 1
    assert v2["version"] == 2
    assert store.latest("KPI_A")["version"] == 1
    assert store.latest_any("KPI_A")["version"] == 2
    assert len(store.history("KPI_A")) == 2


def test_fr501_import_json_and_csv(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path / "kb.json")
    json_path = tmp_path / "seed.json"
    json_path.write_text(
        json.dumps({"records": [{"kpi_name": "A", "approved": True}]}),
        encoding="utf-8",
    )
    csv_path = tmp_path / "seed.csv"
    csv_path.write_text("kpi_name,unit,approved\nB,%,true\n", encoding="utf-8")

    store.import_file(json_path)
    store.import_file(csv_path)

    assert store.latest("A") is not None
    assert store.latest("B")["unit"] == "%"


def test_zero_variance_observation_is_pending_version(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path / "kb.json")
    store.upsert(KnowledgeEntry(kpi_name="KPI_A", unit="%", approved=True, source="SRS"))
    comparison = tmp_path / "comparison.csv"
    pd.DataFrame(
        {
            "kpi_name": ["KPI_A", "KPI_A", "KPI_B"],
            "unit": ["%", "%", "%"],
            "reference_std": [0.0, 1.0, 0.0],
            "comparison_eligible": [True, True, False],
            "comparison_kind": ["FR401", "FR401", "FR402"],
        }
    ).to_csv(comparison, index=False)

    created = ingest_zero_variance_observations(store, [comparison])

    assert len(created) == 1
    latest_any = store.latest_any("KPI_A")
    assert latest_any["approved"] is False
    assert latest_any["source"] == "runtime_fr302_zero_variance"
    note = latest_any["operational_notes"][-1]
    assert note["eligible_zero_variance_rows"] == 1
    assert store.latest("KPI_A")["version"] == 1
