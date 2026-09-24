from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from rkaa.application.report_generator import (
    build_impact_report_model,
    generate_impact_report_excel,
    generate_impact_report_html,
    generate_impact_report_pdf,
)
from rkaa.domain.impact_manager.models import ImpactEvent, ImpactSource, ImpactStatus
from rkaa.domain.knowledge_base import KnowledgeBaseService, KnowledgeEntry, KnowledgeStore


def _impact() -> ImpactEvent:
    return ImpactEvent(
        impact_id="impact-1",
        ne_id="NE-1",
        cell_id="CELL-1",
        t1_utc=datetime(2026, 7, 10, 10, tzinfo=timezone.utc),
        t2_utc=datetime(2026, 7, 10, 10, 30, tzinfo=timezone.utc),
        impact_type="CONFIG_CHANGE",
        description="Thay đổi tham số X",
        operator="engineer-a",
        source=ImpactSource.MANUAL,
        status=ImpactStatus.CLOSED,
        created_at_utc=datetime(2026, 7, 10, 9, tzinfo=timezone.utc),
        updated_at_utc=datetime(2026, 7, 10, 11, tzinfo=timezone.utc),
    )


def _series() -> pd.DataFrame:
    timestamps = pd.date_range("2026-07-09T10:00:00Z", periods=50, freq="1h")
    values = [99.0] * 25 + [95.0] * 25
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "period_end": timestamps + pd.Timedelta(hours=1),
            "ne_id": "NE-1",
            "cell_id": "CELL-1",
            "kpi_name": "KPI_A",
            "value": values,
        }
    )


def _analysis() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "impact_id": "impact-1",
                "ne_id": "NE-1",
                "cell_id": "CELL-1",
                "kpi_name": "KPI_A",
                "temporal_profile": "BUSY",
                "day_type": "WEEKDAY",
                "pre_start": pd.Timestamp("2026-07-09T10:00:00Z"),
                "pre_end": pd.Timestamp("2026-07-10T10:00:00Z"),
                "post_start": pd.Timestamp("2026-07-10T10:30:00Z"),
                "post_end": pd.Timestamp("2026-07-11T10:30:00Z"),
                "pre_mean": 99.0,
                "post_mean": 95.0,
                "delta_abs": -4.0,
                "delta_percent": -4.0404,
                "welch_t_p_value": 0.001,
                "mann_whitney_p_value": 0.002,
                "change_direction": "DECREASE",
                "change_assessment": "DEGRADED",
                "anomaly_flag": True,
                "anomaly_source": "3SIGMA",
                "baseline_mean": 99.1,
            }
        ]
    )


def _knowledge(tmp_path: Path) -> KnowledgeBaseService:
    service = KnowledgeBaseService(KnowledgeStore(tmp_path / "kb.json"))
    service.update(
        KnowledgeEntry(
            kpi_name="KPI_A",
            meaning_increase="Tăng là tốt",
            meaning_decrease="Giảm là xấu",
            approved=True,
            source="test",
        )
    )
    service.save_pattern_suggestion(
        {
            "pattern_id": "pattern-a",
            "status": "APPROVED",
            "impact_type": "CONFIG_CHANGE",
            "kpi_name": "KPI_A",
            "summary": "CONFIG_CHANGE thường làm KPI_A giảm.",
        }
    )
    return service


def test_fr601_model_reuses_fr301_fr302_fr502_and_approved_fr503(tmp_path: Path) -> None:
    model = build_impact_report_model(
        _series(),
        _impact(),
        _analysis(),
        knowledge_base=_knowledge(tmp_path),
    )
    assert len(model.charts) == 1
    assert model.knowledge_rows.iloc[0]["knowledge_meaning"] == "Giảm là xấu"
    assert model.approved_patterns[0]["pattern_id"] == "pattern-a"
    assert "suy giảm" in model.overall_conclusion


def test_fr601_generates_html_pdf_and_excel(tmp_path: Path) -> None:
    model = build_impact_report_model(
        _series(),
        _impact(),
        _analysis(),
        knowledge_base=_knowledge(tmp_path),
    )
    html = generate_impact_report_html(model, tmp_path / "impact.html")
    pdf = generate_impact_report_pdf(model, tmp_path / "impact.pdf")
    xlsx = generate_impact_report_excel(model, tmp_path / "impact.xlsx")

    text = html.read_text(encoding="utf-8")
    assert "Tóm tắt điều hành" in text
    assert "Thay đổi tham số X" in text
    assert "Giảm là xấu" in text
    assert "CONFIG_CHANGE thường làm KPI_A giảm." in text
    assert pdf.stat().st_size > 1000
    assert xlsx.stat().st_size > 1000

    book = pd.ExcelFile(xlsx)
    assert {"Summary", "Impact", "KPI Delta", "Knowledge", "Patterns", "Charts"}.issubset(
        set(book.sheet_names)
    )
