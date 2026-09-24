from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from rkaa.domain.knowledge_base import KnowledgeBaseService, KnowledgeStore
from rkaa.domain.pattern_learner import PatternLearnerService


def _history(count: int) -> pd.DataFrame:
    rows = []
    for idx in range(count):
        impact_id = f"impact-{idx}"
        # two temporal rows for the same impact must still count as one event
        for profile, delta in (("BUSY", -4.0 - idx * 0.1), ("OFF_PEAK", -4.2 - idx * 0.1)):
            rows.append(
                {
                    "impact_id": impact_id,
                    "impact_type": "CONFIG_CHANGE",
                    "kpi_name": "KPI_A",
                    "temporal_profile": profile,
                    "change_direction": "DECREASE",
                    "change_assessment": "DEGRADED",
                    "delta_percent": delta,
                }
            )
    return pd.DataFrame(rows)


def test_fr503_requires_five_distinct_similar_impacts(tmp_path: Path) -> None:
    service = KnowledgeBaseService(KnowledgeStore(tmp_path / "kb.json"))
    learner = PatternLearnerService(service)

    assert learner.suggest(_history(4)) == []

    suggestions = learner.suggest(_history(5))
    assert len(suggestions) == 1
    pattern = suggestions[0]
    assert pattern["status"] == "PENDING"
    assert pattern["occurrence_count"] == 5
    assert pattern["impact_type"] == "CONFIG_CHANGE"
    assert pattern["kpi_name"] == "KPI_A"
    assert "5 sự kiện tương tự" in pattern["summary"]


def test_fr503_engineer_can_edit_approve_reject_and_approved_pattern_is_in_kb(
    tmp_path: Path,
) -> None:
    service = KnowledgeBaseService(KnowledgeStore(tmp_path / "kb.json"))
    learner = PatternLearnerService(service)
    pattern = learner.suggest(_history(5))[0]

    edited = learner.edit(
        pattern["pattern_id"],
        edited_by="engineer-a",
        reviewer_role="Engineer",
        summary="Pattern đã được kỹ sư hiệu chỉnh.",
    )
    assert edited["status"] == "PENDING"
    assert edited["summary"] == "Pattern đã được kỹ sư hiệu chỉnh."

    approved = learner.approve(
        pattern["pattern_id"],
        approved_by="engineer-a",
        approver_role="Engineer",
        edited_summary="Pattern được phê duyệt.",
    )
    assert approved["status"] == "APPROVED"
    assert service.approved_patterns_for_kpi("KPI_A")[0]["summary"] == "Pattern được phê duyệt."

    with pytest.raises(PermissionError):
        learner.reject(
            pattern["pattern_id"],
            rejected_by="reader",
            reviewer_role="ReadOnly",
        )


def test_fr503_recovery_is_only_reported_when_source_data_contains_it(tmp_path: Path) -> None:
    service = KnowledgeBaseService(KnowledgeStore(tmp_path / "kb.json"))
    learner = PatternLearnerService(service)
    history = _history(5)
    history["recovery_hours"] = 2.5
    pattern = learner.suggest(history)[0]
    assert pattern["recovery_hours"] == 2.5
    assert "phục hồi" in pattern["summary"]
