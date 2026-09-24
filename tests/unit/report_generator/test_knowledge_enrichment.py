from __future__ import annotations

from pathlib import Path

import pandas as pd

from rkaa.application.report_generator import enrich_kpi_changes_with_knowledge
from rkaa.domain.knowledge_base import KnowledgeBaseService, KnowledgeEntry, KnowledgeStore


def test_fr502_enriches_each_affected_kpi_by_change_direction(tmp_path: Path) -> None:
    service = KnowledgeBaseService(KnowledgeStore(tmp_path / "kb.json"))
    service.update(
        KnowledgeEntry(
            kpi_name="KPI_A",
            meaning_increase="Increase meaning",
            meaning_decrease="Decrease meaning",
            approved=True,
        )
    )
    frame = pd.DataFrame(
        [
            {"kpi_name": "KPI_A", "delta_abs": 2.0},
            {"kpi_name": "KPI_A", "delta_abs": -3.0},
            {"kpi_name": "UNKNOWN", "delta_abs": 1.0},
        ]
    )

    result = enrich_kpi_changes_with_knowledge(frame, service)

    assert result.loc[0, "knowledge_meaning"] == "Increase meaning"
    assert result.loc[1, "knowledge_meaning"] == "Decrease meaning"
    assert result.loc[2, "knowledge_meaning"] == "Chưa có tri thức — cần cập nhật"
    assert list(result["knowledge_status"]) == ["FOUND", "FOUND", "MISSING"]


def test_fr502_without_store_explicitly_marks_missing_knowledge() -> None:
    frame = pd.DataFrame([{"kpi_name": "KPI_A", "delta_abs": 1.0}])
    result = enrich_kpi_changes_with_knowledge(frame, None)
    assert result.loc[0, "knowledge_meaning"] == "Chưa có tri thức — cần cập nhật"
