"""FR-502 report enrichment using approved FR-501 knowledge."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from rkaa.domain.knowledge_base import KnowledgeBaseService

_KNOWLEDGE_COLUMNS = (
    "knowledge_status",
    "knowledge_available",
    "knowledge_version",
    "knowledge_meaning",
    "knowledge_source",
)


def _direction_from_delta(value: Any) -> str:
    try:
        delta = float(value)
    except (TypeError, ValueError):
        return "NO_CHANGE"
    if not np.isfinite(delta) or abs(delta) <= 1e-12:
        return "NO_CHANGE"
    return "INCREASE" if delta > 0 else "DECREASE"


def enrich_kpi_changes_with_knowledge(
    frame: pd.DataFrame,
    service: KnowledgeBaseService | None,
    *,
    kpi_column: str = "kpi_name",
    delta_column: str = "delta_abs",
) -> pd.DataFrame:
    """Attach FR-502 meaning to every KPI change row.

    This helper is report-format agnostic and can consume FR-301/FR-302 output
    directly.  Only the latest approved knowledge version is used through
    :class:`KnowledgeBaseService`.  Missing knowledge is explicitly marked as
    required by FR-502.
    """

    if kpi_column not in frame.columns:
        raise ValueError(f"FR-502 thiếu cột KPI: {kpi_column}")
    if delta_column not in frame.columns:
        raise ValueError(f"FR-502 thiếu cột delta: {delta_column}")

    work = frame.copy()
    if work.empty:
        for column in _KNOWLEDGE_COLUMNS:
            work[column] = pd.Series(dtype="object")
        return work

    explanations: list[dict[str, Any]] = []
    for row in work.itertuples(index=False):
        kpi_name = str(getattr(row, kpi_column))
        direction = _direction_from_delta(getattr(row, delta_column))
        if service is None:
            explanation = {
                "knowledge_status": "MISSING",
                "knowledge_available": False,
                "knowledge_version": None,
                "knowledge_meaning": "Chưa có tri thức — cần cập nhật",
                "knowledge_source": "",
            }
        else:
            explanation = service.explain_change(kpi_name, direction=direction)
        explanations.append(explanation)

    for column in _KNOWLEDGE_COLUMNS:
        work[column] = [item.get(column) for item in explanations]
    return work


__all__ = ["enrich_kpi_changes_with_knowledge"]
