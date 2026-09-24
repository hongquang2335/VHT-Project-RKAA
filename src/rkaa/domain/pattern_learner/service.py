"""FR-503 pattern learning built on the existing Knowledge Base authority."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from rkaa.domain.knowledge_base import KnowledgeBaseService

_REQUIRED_HISTORY = {
    "impact_id",
    "impact_type",
    "kpi_name",
    "change_direction",
    "delta_percent",
}


@dataclass(frozen=True, slots=True)
class PatternLearnerConfig:
    """Configuration for FR-503 repeated-impact pattern suggestions."""

    minimum_similar_events: int = 5

    def __post_init__(self) -> None:
        if self.minimum_similar_events < 5:
            raise ValueError("FR-503 yêu cầu tối thiểu 5 sự kiện tương tự")


class PatternLearnerService:
    """Detect repeated impact/KPI outcomes and persist suggestions into FR-501 KB.

    Similarity is deliberately deterministic and auditable: one event-level
    observation per ``impact_id`` is formed for the same impact type, KPI,
    direction and assessment.  Only groups with at least five distinct impacts
    become suggestions.  Multiple temporal-profile rows from a single impact
    therefore never inflate the occurrence count.
    """

    def __init__(
        self,
        knowledge_base: KnowledgeBaseService,
        *,
        config: PatternLearnerConfig = PatternLearnerConfig(),
    ) -> None:
        self.knowledge_base = knowledge_base
        self.config = config

    @staticmethod
    def _pattern_id(
        impact_type: str,
        kpi_name: str,
        direction: str,
        assessment: str,
    ) -> str:
        raw = "|".join([impact_type, kpi_name, direction, assessment])
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"pattern-{digest}"

    @staticmethod
    def _summary(
        *,
        impact_type: str,
        kpi_name: str,
        direction: str,
        occurrence_count: int,
        median_delta_percent: float,
        recovery_hours: float | None,
    ) -> str:
        if direction == "INCREASE":
            verb = "tăng"
        elif direction == "DECREASE":
            verb = "giảm"
        else:
            verb = "thay đổi"
        magnitude = abs(float(median_delta_percent))
        text = (
            f"{impact_type} thường làm {kpi_name} {verb} khoảng "
            f"{magnitude:.2f}% qua {occurrence_count} sự kiện tương tự"
        )
        if recovery_hours is not None and np.isfinite(recovery_hours):
            text += f", thời gian phục hồi điển hình khoảng {float(recovery_hours):.2f} giờ"
        return text + "."

    def suggest(self, analysis_history: pd.DataFrame) -> list[dict[str, Any]]:
        """Create/update pending suggestions from historical FR-301 results."""

        missing = sorted(_REQUIRED_HISTORY.difference(analysis_history.columns))
        if missing:
            raise ValueError(f"FR-503 thiếu dữ liệu lịch sử: {', '.join(missing)}")
        if analysis_history.empty:
            return []

        work = analysis_history.copy()
        work["delta_percent"] = pd.to_numeric(work["delta_percent"], errors="coerce")
        work = work.dropna(subset=["impact_id", "impact_type", "kpi_name", "delta_percent"])
        work["change_direction"] = work["change_direction"].astype(str).str.upper()
        work = work[work["change_direction"].isin({"INCREASE", "DECREASE"})]
        if work.empty:
            return []

        if "change_assessment" not in work.columns:
            work["change_assessment"] = "INFORMATIONAL_CHANGE"
        work["change_assessment"] = work["change_assessment"].fillna(
            "INFORMATIONAL_CHANGE"
        ).astype(str)

        # Collapse temporal-profile/day-type rows to one observation per Impact Event.
        event_keys = [
            "impact_id",
            "impact_type",
            "kpi_name",
            "change_direction",
            "change_assessment",
        ]
        aggregations: dict[str, Any] = {"delta_percent": "median"}
        if "recovery_hours" in work.columns:
            work["recovery_hours"] = pd.to_numeric(work["recovery_hours"], errors="coerce")
            aggregations["recovery_hours"] = "median"
        event_level = work.groupby(event_keys, dropna=False, as_index=False).agg(aggregations)

        group_keys = [
            "impact_type",
            "kpi_name",
            "change_direction",
            "change_assessment",
        ]
        suggestions: list[dict[str, Any]] = []
        for key, group in event_level.groupby(group_keys, dropna=False, sort=True):
            impact_type, kpi_name, direction, assessment = [str(item) for item in key]
            count = int(group["impact_id"].nunique())
            if count < self.config.minimum_similar_events:
                continue
            median_delta = float(group["delta_percent"].median())
            recovery: float | None = None
            if "recovery_hours" in group.columns:
                finite = pd.to_numeric(group["recovery_hours"], errors="coerce").dropna()
                if not finite.empty:
                    recovery = float(finite.median())

            pattern_id = self._pattern_id(impact_type, kpi_name, direction, assessment)
            existing = self.knowledge_base.store.get_pattern(pattern_id)
            # Never silently overwrite an engineer's approved/rejected decision.
            if existing is not None and str(existing.get("status", "")).upper() in {
                "APPROVED",
                "REJECTED",
            }:
                suggestions.append(existing)
                continue

            record = {
                "pattern_id": pattern_id,
                "status": "PENDING",
                "impact_type": impact_type,
                "kpi_name": kpi_name,
                "change_direction": direction,
                "change_assessment": assessment,
                "occurrence_count": count,
                "median_delta_percent": median_delta,
                "recovery_hours": recovery,
                "source": "FR503_PATTERN_LEARNER",
                "summary": self._summary(
                    impact_type=impact_type,
                    kpi_name=kpi_name,
                    direction=direction,
                    occurrence_count=count,
                    median_delta_percent=median_delta,
                    recovery_hours=recovery,
                ),
            }
            suggestions.append(self.knowledge_base.save_pattern_suggestion(record))
        return suggestions

    def approve(
        self,
        pattern_id: str,
        *,
        approved_by: str,
        approver_role: str,
        edited_summary: str | None = None,
    ) -> dict[str, Any]:
        return self.knowledge_base.review_pattern(
            pattern_id,
            action="APPROVE",
            reviewed_by=approved_by,
            reviewer_role=approver_role,
            edited_summary=edited_summary,
        )

    def reject(
        self,
        pattern_id: str,
        *,
        rejected_by: str,
        reviewer_role: str,
    ) -> dict[str, Any]:
        return self.knowledge_base.review_pattern(
            pattern_id,
            action="REJECT",
            reviewed_by=rejected_by,
            reviewer_role=reviewer_role,
        )

    def edit(
        self,
        pattern_id: str,
        *,
        edited_by: str,
        reviewer_role: str,
        summary: str,
    ) -> dict[str, Any]:
        return self.knowledge_base.review_pattern(
            pattern_id,
            action="EDIT",
            reviewed_by=edited_by,
            reviewer_role=reviewer_role,
            edited_summary=summary,
        )
