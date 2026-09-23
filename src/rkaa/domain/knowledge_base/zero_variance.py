"""Runtime FR-302 zero-variance observations persisted into FR-501 knowledge history."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from .store import KnowledgeEntry, KnowledgeStore


def ingest_zero_variance_observations(
    store: KnowledgeStore,
    comparison_paths: Iterable[str | Path],
    *,
    epsilon: float = 1e-12,
    created_by: str = "runtime-detector",
) -> list[dict[str, object]]:
    """Create pending knowledge versions for KPI with eligible std=0 references.

    These observations are deliberately unapproved. They document that 3-sigma
    was not applicable and that operational FR-303 thresholds should be used
    when configured; an engineer can later approve/edit them.
    """

    frames: list[pd.DataFrame] = []
    sources: list[str] = []
    for raw_path in comparison_paths:
        path = Path(raw_path)
        frame = pd.read_csv(path)
        if "kpi_name" not in frame.columns or "reference_std" not in frame.columns:
            continue
        eligible = (
            frame.get("comparison_eligible", pd.Series(True, index=frame.index))
            .fillna(False)
            .astype(bool)
        )
        std = pd.to_numeric(frame["reference_std"], errors="coerce")
        mask = eligible & std.notna() & np.isfinite(std) & (std.abs() <= epsilon)
        selected = frame.loc[mask].copy()
        if selected.empty:
            continue
        selected["_source_file"] = path.name
        frames.append(selected)
        sources.append(path.name)

    if not frames:
        return []

    all_rows = pd.concat(frames, ignore_index=True)
    created: list[dict[str, object]] = []
    for kpi_name, group in all_rows.groupby("kpi_name", sort=True):
        latest = store.latest_any(str(kpi_name)) or {}
        notes = list(latest.get("operational_notes") or [])
        observation = {
            "kind": "FR302_ZERO_VARIANCE",
            "status": "PENDING_ENGINEER_REVIEW",
            "eligible_zero_variance_rows": int(len(group)),
            "comparison_kinds": sorted(
                set(group.get("comparison_kind", pd.Series(dtype=str)).dropna().astype(str))
            ),
            "source_files": sorted(set(group["_source_file"].astype(str))),
            "guidance": (
                "reference_std=0 => 3-sigma không áp dụng; ưu tiên FR-303 threshold "
                "nếu người vận hành đã cấu hình."
            ),
        }
        # Avoid duplicating exactly the same runtime observation on repeated demos.
        signature = (
            observation["kind"],
            observation["eligible_zero_variance_rows"],
            tuple(observation["source_files"]),
        )
        existing_signatures = {
            (
                item.get("kind"),
                item.get("eligible_zero_variance_rows"),
                tuple(item.get("source_files", [])),
            )
            for item in notes
            if isinstance(item, dict)
        }
        if signature in existing_signatures:
            continue
        notes.append(observation)
        entry = KnowledgeEntry(
            kpi_name=str(kpi_name),
            display_name=str(latest.get("display_name") or kpi_name),
            unit=str(group.get("unit", pd.Series([latest.get("unit", "")])).dropna().astype(str).head(1).iloc[0] if "unit" in group.columns and group["unit"].notna().any() else latest.get("unit", "")),
            description=str(latest.get("description", "")),
            direction_preference=str(latest.get("direction_preference", "informational")),
            meaning_increase=str(latest.get("meaning_increase", "")),
            meaning_decrease=str(latest.get("meaning_decrease", "")),
            common_causes_increase=list(latest.get("common_causes_increase") or []),
            common_causes_decrease=list(latest.get("common_causes_decrease") or []),
            related_kpis=list(latest.get("related_kpis") or []),
            reference_thresholds=dict(latest.get("reference_thresholds") or {}),
            operational_notes=notes,
            source="runtime_fr302_zero_variance",
            approved=False,
            created_by=created_by,
        )
        created.append(store.upsert(entry))
    return created
