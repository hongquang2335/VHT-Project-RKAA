from __future__ import annotations

from pathlib import Path

import pytest

from rkaa.domain.knowledge_base import KnowledgeBaseService, KnowledgeEntry, KnowledgeStore


def test_fr501_service_get_search_update_and_history_reuse_store(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path / "kb.json")
    service = KnowledgeBaseService(store)

    first = service.update(
        KnowledgeEntry(
            kpi_name="KPI_A",
            display_name="KPI Alpha",
            description="Setup success KPI",
            meaning_increase="Tốt hơn",
            meaning_decrease="Xấu hơn",
            related_kpis=["KPI_B"],
            approved=True,
            source="manual",
        )
    )
    second = service.update(
        KnowledgeEntry(
            kpi_name="KPI_A",
            display_name="KPI Alpha",
            description="Pending edit",
            meaning_increase="Bản mới",
            meaning_decrease="Bản mới",
            approved=False,
            source="manual",
        )
    )

    assert first["version"] == 1
    assert second["version"] == 2
    assert service.get("KPI_A")["version"] == 1
    assert service.get("KPI_A", approved_only=False)["version"] == 2
    assert len(service.history("KPI_A")) == 2
    assert service.search("setup")[0]["kpi_name"] == "KPI_A"
    assert service.search("KPI_B")[0]["kpi_name"] == "KPI_A"


def test_fr501_approval_enforces_br06_role(tmp_path: Path) -> None:
    service = KnowledgeBaseService(KnowledgeStore(tmp_path / "kb.json"))
    pending = service.update(KnowledgeEntry(kpi_name="KPI_A", approved=False))

    with pytest.raises(PermissionError):
        service.approve(
            "KPI_A",
            pending["version"],
            approved_by="reader",
            approver_role="ReadOnly",
        )

    approved = service.approve(
        "KPI_A",
        pending["version"],
        approved_by="engineer-a",
        approver_role="Engineer",
    )
    assert approved["approved"] is True
    assert approved["approved_by"] == "engineer-a"
    assert approved["approver_role"] == "engineer"


def test_fr502_explanation_uses_latest_approved_version_only(tmp_path: Path) -> None:
    service = KnowledgeBaseService(KnowledgeStore(tmp_path / "kb.json"))
    service.update(
        KnowledgeEntry(
            kpi_name="KPI_A",
            meaning_increase="approved increase meaning",
            meaning_decrease="approved decrease meaning",
            approved=True,
            source="v1",
        )
    )
    service.update(
        KnowledgeEntry(
            kpi_name="KPI_A",
            meaning_increase="pending meaning",
            meaning_decrease="pending meaning",
            approved=False,
            source="v2",
        )
    )

    explanation = service.explain_change("KPI_A", direction="DECREASE")
    assert explanation["knowledge_status"] == "FOUND"
    assert explanation["knowledge_version"] == 1
    assert explanation["knowledge_meaning"] == "approved decrease meaning"
    assert explanation["knowledge_source"] == "v1"

    missing = service.explain_change("UNKNOWN", direction="INCREASE")
    assert missing["knowledge_status"] == "MISSING"
    assert missing["knowledge_meaning"] == "Chưa có tri thức — cần cập nhật"
