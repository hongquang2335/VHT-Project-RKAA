from __future__ import annotations

from pathlib import Path

import pandas as pd

from rkaa.application.report_generator import (
    HealthReportArtifacts,
    build_report_model,
    generate_health_report_html,
    generate_health_report_pdf,
    prepare_health_input,
    select_distinctive_day,
    select_health_period,
)


from rkaa.application.report_generator.health_report import FOCUS7_KPIS

def _frame() -> pd.DataFrame:
    ts = pd.date_range("2026-01-01T00:00:00Z", periods=16 * 24, freq="h")
    rows = []
    for hour, timestamp in enumerate(ts):
        day = hour // 24
        value = 100.0 + (10.0 if day == 5 else 0.0) + (hour % 24) * 0.01
        rows.append(
            {
                "timestamp": timestamp,
                "ne_id": "NE1",
                "cell_id": "CELL1",
                "kpi_name": FOCUS7_KPIS[0],
                "value": value,
                "unit": "%",
                "is_counter": False,
            }
        )
    return pd.DataFrame(rows)


def test_distinctive_day_selects_injected_shift() -> None:
    df = prepare_health_input(_frame())
    day, score = select_distinctive_day(df)
    assert day == "2026-01-06"
    assert score > 0


def test_daily_period_uses_three_defined_cycle_references() -> None:
    df = prepare_health_input(_frame())
    day = select_health_period(df, "last-day")

    assert day.end - day.start == pd.Timedelta(hours=24)
    assert len(day.references) == 3
    assert [(day.end - ref.start).total_seconds() / 3600 for ref in day.references] == [
        72,
        144,
        288,
    ]
    assert all(ref.end == day.start for ref in day.references)
    assert all(ref.aggregation == "mean_daily_cycle" for ref in day.references)


def test_week_period_uses_current_and_immediately_previous_seven_days() -> None:
    df = prepare_health_input(_frame())
    week = select_health_period(df, "last-week")

    assert week.end - week.start == pd.Timedelta(days=7)
    assert len(week.references) == 1
    reference = week.references[0]
    assert reference.end == week.start
    assert reference.end - reference.start == pd.Timedelta(days=7)
    assert reference.aggregation == "direct_window"


def test_report_model_daily_has_three_reference_rows_per_kpi() -> None:
    model = build_report_model(_frame(), period_kind="last-day")
    assert len(model.kpi_summary) == 3
    assert model.kpi_summary["reference_label"].nunique() == 3


def test_health_report_html_uses_user_facing_sections_and_no_requirement_ids(tmp_path: Path) -> None:
    output, period, metadata = generate_health_report_html(
        _frame(),
        period_kind="last-day",
        output_path=tmp_path / "report.html",
        artifacts=HealthReportArtifacts(),
    )
    text = output.read_text(encoding="utf-8")

    assert period.kind == "last-day"
    assert metadata["kpi_count"] == 1
    assert "Tóm tắt điều hành" in text
    assert "Tổng hợp KPI theo NE" in text
    assert "Danh sách NE có xu hướng suy giảm" in text
    assert "Bất thường được phát hiện trong kỳ" in text
    assert "5 cặp NE-Cell nổi bật" not in text
    assert "Điểm thay đổi" not in text
    assert "Giải thích ý nghĩa KPI từ cơ sở tri thức" not in text
    assert "FR-" not in text
    assert 'name="viewport"' in text


def test_health_report_pdf_is_generated(tmp_path: Path) -> None:
    output, period, metadata = generate_health_report_pdf(
        _frame(),
        period_kind="last-week",
        output_path=tmp_path / "report.pdf",
        artifacts=HealthReportArtifacts(),
    )

    assert period.kind == "last-week"
    assert metadata["kpi_count"] == 1
    assert output.exists()
    assert output.stat().st_size > 1000
    assert output.read_bytes()[:4] == b"%PDF"



def test_prepare_health_input_keeps_only_focus7() -> None:
    frame = _frame()
    extra = frame.iloc[:1].copy()
    extra["kpi_name"] = "5G RASR CB (%)"
    result = prepare_health_input(pd.concat([frame, extra], ignore_index=True))
    assert set(result["kpi_name"]) == {FOCUS7_KPIS[0]}


def _comparison_for_top_pairs(current_end: pd.Timestamp) -> pd.DataFrame:
    rows = []
    # Pair 1 -> 5 anomalous KPI, pair 2 -> 4, ... pair 6 -> 0.
    for pair_index in range(1, 7):
        anomalous_count = max(0, 6 - pair_index)
        for kpi_index, kpi in enumerate(FOCUS7_KPIS):
            is_anomaly = kpi_index < anomalous_count
            rows.append(
                {
                    "ne_id": f"NE{pair_index}",
                    "cell_id": f"CELL{pair_index}",
                    "kpi_name": kpi,
                    "temporal_profile": "BUSY",
                    "reference_label": "24H_TO_72H_AVG",
                    "current_mean": 100.0 + pair_index,
                    "reference_mean": 100.0,
                    "delta_percent": float(pair_index),
                    "sigma_applicable": True,
                    "reference_z_score": 3.5 if is_anomaly else 0.5,
                    "anomaly_3sigma": is_anomaly,
                    "anomaly_flag": is_anomaly,
                    "anomaly_decision_source": "FR302_3SIGMA",
                    "current_end": current_end.isoformat(),
                }
            )
    # Auxiliary KPI must never affect pair ranking.
    rows.append(
        {
            "ne_id": "NE6",
            "cell_id": "CELL6",
            "kpi_name": "5G RASR CB (%)",
            "temporal_profile": "BUSY",
            "reference_label": "24H_TO_72H_AVG",
            "current_mean": 999.0,
            "reference_mean": 1.0,
            "delta_percent": 99900.0,
            "sigma_applicable": True,
            "anomaly_flag": True,
            "anomaly_decision_source": "FR302_3SIGMA",
            "current_end": current_end.isoformat(),
        }
    )
    return pd.DataFrame(rows)


def test_report_ranks_top5_ne_cell_by_distinct_anomalous_focus_kpis_and_keeps_all_7_rows(
    tmp_path: Path,
) -> None:
    prepared = prepare_health_input(_frame())
    period = select_health_period(prepared, "last-day")
    comparison = _comparison_for_top_pairs(period.end)
    comparison_path = tmp_path / "daily_comparison.csv"
    comparison.to_csv(comparison_path, index=False)

    model = build_report_model(
        _frame(),
        period_kind="last-day",
        artifacts=HealthReportArtifacts(fr401_comparison=comparison_path),
    )
    ranking = model.detection["top_pairs"]
    detail = model.detection["top_pair_kpis"]

    assert len(ranking) == 5
    assert ranking.iloc[0]["ne_id"] == "NE1"
    assert int(ranking.iloc[0]["anomalous_kpi_count"]) == 5
    assert "NE6" not in set(ranking["ne_id"])
    assert len(detail) == 5 * 7
    assert detail.groupby(["ne_id", "cell_id"]).size().eq(7).all()
    assert set(detail["kpi_name"]) == set(FOCUS7_KPIS)


def test_html_lists_every_anomaly_with_comparison_reason_and_chart(tmp_path: Path) -> None:
    prepared = prepare_health_input(_frame())
    period = select_health_period(prepared, "last-day")
    comparison_path = tmp_path / "daily_comparison.csv"
    _comparison_for_top_pairs(period.end).to_csv(comparison_path, index=False)

    output, _, metadata = generate_health_report_html(
        _frame(),
        period_kind="last-day",
        output_path=tmp_path / "report_focus7.html",
        artifacts=HealthReportArtifacts(fr401_comparison=comparison_path),
    )
    text = output.read_text(encoding="utf-8")
    model = build_report_model(
        _frame(),
        period_kind="last-day",
        artifacts=HealthReportArtifacts(fr401_comparison=comparison_path),
    )
    assert metadata["focus_kpi_count"] == 7
    assert len(model.anomaly_details) == 15
    assert "Bất thường được phát hiện trong kỳ" in text
    assert "So với" in text
    assert "Lý do gắn cờ" in text
    assert "Nguyên nhân vận hành" not in text
    assert "quy tắc 3-sigma" in text
    assert "Biểu đồ 1" in text
    assert "Biểu đồ 2" in text
    assert "data:image/png;base64" in text
    assert "5 cặp NE-Cell nổi bật" not in text
    assert "5G RASR CB (%)" not in text


def test_hierarchy_summary_does_not_invent_region_or_site() -> None:
    model = build_report_model(_frame(), period_kind="last-day")
    assert set(model.hierarchy_summary["level"]) == {"NE"}
    assert set(model.hierarchy_summary["entity"]) == {"NE1"}


def test_degrading_ne_list_uses_trend_artifact_and_focus7_only(tmp_path: Path) -> None:
    trend = pd.DataFrame(
        [
            {"ne_id": "NE1", "cell_id": "CELL1", "kpi_name": FOCUS7_KPIS[0], "trend_label": "degrading"},
            {"ne_id": "NE1", "cell_id": "CELL2", "kpi_name": FOCUS7_KPIS[1], "trend_label": "degrading"},
            {"ne_id": "NE2", "cell_id": "CELL3", "kpi_name": "5G RASR CB (%)", "trend_label": "degrading"},
        ]
    )
    trend_path = tmp_path / "trend.csv"
    trend.to_csv(trend_path, index=False)
    model = build_report_model(
        _frame(),
        period_kind="last-day",
        artifacts=HealthReportArtifacts(trend_summary=trend_path),
    )
    assert list(model.degrading_ne["ne_id"]) == ["NE1"]
    assert int(model.degrading_ne.iloc[0]["degrading_kpi_count"]) == 2


def test_ne_summary_html_shows_each_ne_id_once_with_rowspan(tmp_path: Path) -> None:
    frame = _frame()
    second = frame.copy()
    second["kpi_name"] = FOCUS7_KPIS[1]
    both = pd.concat([frame, second], ignore_index=True)
    output, _, _ = generate_health_report_html(
        both,
        period_kind="last-day",
        output_path=tmp_path / "ne_summary.html",
        artifacts=HealthReportArtifacts(),
    )
    text = output.read_text(encoding="utf-8")
    assert 'rowspan="2" class="ne-id"><b>NE1</b>' in text



def test_anomaly_detail_keeps_flag_so_both_companion_charts_have_shaded_spans(tmp_path: Path) -> None:
    from rkaa.application.report_generator.health_report import _anomaly_spans_for_pair_kpi

    prepared = prepare_health_input(_frame())
    period = select_health_period(prepared, "last-day")
    comparison_path = tmp_path / "daily_comparison.csv"
    _comparison_for_top_pairs(period.end).to_csv(comparison_path, index=False)

    model = build_report_model(
        _frame(),
        period_kind="last-day",
        artifacts=HealthReportArtifacts(fr401_comparison=comparison_path),
    )
    assert not model.anomaly_details.empty
    assert model.anomaly_details["anomaly_flag"].all()

    row = model.anomaly_details.iloc[0]
    spans = _anomaly_spans_for_pair_kpi(
        {"aligned_frame": pd.DataFrame([row])},
        period,
        str(row["ne_id"]),
        str(row["cell_id"]),
        str(row["kpi_name"]),
    )
    assert spans
    assert all(profile in {"BUSY", "TRANSITION", "OFF_PEAK"} for _, _, profile in spans)


def test_machine_reference_label_maps_to_daily_reference_period() -> None:
    from rkaa.application.report_generator.health_report import _reference_period_by_label

    prepared = prepare_health_input(_frame())
    period = select_health_period(prepared, "last-day")
    reference = _reference_period_by_label(period, "24H_TO_144H_AVG")
    assert reference is not None
    assert int((period.end - reference.start).total_seconds() / 3600) == 144
