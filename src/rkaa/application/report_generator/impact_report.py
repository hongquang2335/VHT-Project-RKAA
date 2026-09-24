"""FR-601 Impact Report built from FR-301/302 and FR-501/502/503 cores."""

from __future__ import annotations

import base64
import io
import textwrap
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

from rkaa.domain.impact_manager.models import ImpactEvent
from rkaa.domain.knowledge_base import KnowledgeBaseService

from .knowledge import enrich_kpi_changes_with_knowledge

_REQUIRED_ANALYSIS = {
    "ne_id",
    "cell_id",
    "kpi_name",
    "pre_mean",
    "post_mean",
    "delta_abs",
    "delta_percent",
    "change_assessment",
    "anomaly_flag",
}
_REQUIRED_SERIES = {"timestamp", "ne_id", "cell_id", "kpi_name", "value"}


@dataclass(frozen=True, slots=True)
class ImpactReportModel:
    impact: ImpactEvent
    analysis: pd.DataFrame
    knowledge_rows: pd.DataFrame
    approved_patterns: tuple[dict[str, Any], ...]
    charts: tuple[tuple[str, bytes], ...]
    executive_summary: tuple[str, ...]
    overall_conclusion: str


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        text = str(value).strip()
        return text or "—"
    if not np.isfinite(number):
        return "—"
    return f"{number:.{digits}f}"


def _normalize_analysis(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(_REQUIRED_ANALYSIS.difference(frame.columns))
    if missing:
        raise ValueError(f"FR-601 thiếu kết quả FR-301/302: {', '.join(missing)}")
    out = frame.copy()
    if "temporal_profile" not in out.columns:
        out["temporal_profile"] = ""
    if "day_type" not in out.columns:
        out["day_type"] = ""
    return out.reset_index(drop=True)


def _affected_keys(frame: pd.DataFrame) -> list[tuple[str, str, str]]:
    if frame.empty:
        return []
    anomaly = frame["anomaly_flag"].fillna(False).astype(bool)
    changed = frame["change_assessment"].fillna("NO_CHANGE").astype(str).ne("NO_CHANGE")
    affected = frame[anomaly | changed]
    keys = {
        (str(row.ne_id), str(row.cell_id), str(row.kpi_name))
        for row in affected.itertuples(index=False)
    }
    return sorted(keys)


def _impact_chart(
    clean_df: pd.DataFrame,
    impact: ImpactEvent,
    analysis: pd.DataFrame,
    ne_id: str,
    cell_id: str,
    kpi_name: str,
) -> bytes:
    missing = sorted(_REQUIRED_SERIES.difference(clean_df.columns))
    if missing:
        raise ValueError(f"FR-601 thiếu time series để vẽ chart: {', '.join(missing)}")

    data = clean_df.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], errors="coerce", utc=True, format="mixed")
    data["value"] = pd.to_numeric(data["value"], errors="coerce")
    data = data.dropna(subset=["timestamp", "value"])
    series = data[
        (data["ne_id"].astype(str) == ne_id)
        & (data["cell_id"].astype(str) == cell_id)
        & (data["kpi_name"].astype(str) == kpi_name)
    ].copy()

    rows = analysis[
        (analysis["ne_id"].astype(str) == ne_id)
        & (analysis["cell_id"].astype(str) == cell_id)
        & (analysis["kpi_name"].astype(str) == kpi_name)
    ]
    t1 = pd.Timestamp(impact.t1_utc)
    t2 = pd.Timestamp(impact.t2_utc) if impact.t2_utc is not None else t1
    if t1.tzinfo is None:
        t1 = t1.tz_localize("UTC")
    else:
        t1 = t1.tz_convert("UTC")
    if t2.tzinfo is None:
        t2 = t2.tz_localize("UTC")
    else:
        t2 = t2.tz_convert("UTC")

    if not rows.empty and "pre_start" in rows.columns and "post_end" in rows.columns:
        start = pd.to_datetime(rows["pre_start"], errors="coerce", utc=True).min()
        end = pd.to_datetime(rows["post_end"], errors="coerce", utc=True).max()
    else:
        start = t1 - pd.Timedelta(hours=24)
        end = t2 + pd.Timedelta(hours=24)
    series = series[(series["timestamp"] >= start) & (series["timestamp"] < end)]

    fig, ax = plt.subplots(figsize=(9.0, 3.4))
    pre = series[series["timestamp"] < t1]
    post = series[series["timestamp"] >= t2]
    between = series[(series["timestamp"] >= t1) & (series["timestamp"] < t2)]
    if not pre.empty:
        ax.plot(pre["timestamp"], pre["value"], linewidth=1.2, label="Trước tác động")
    if not between.empty:
        ax.plot(between["timestamp"], between["value"], linewidth=1.0, label="Trong tác động")
    if not post.empty:
        ax.plot(post["timestamp"], post["value"], linewidth=1.2, label="Sau tác động")
    ax.axvspan(t1, t2, alpha=0.18, label="Impact Window")

    baseline_values = pd.to_numeric(rows.get("baseline_mean"), errors="coerce") if "baseline_mean" in rows else pd.Series(dtype=float)
    if not baseline_values.dropna().empty:
        ax.axhline(
            float(baseline_values.dropna().median()),
            linestyle="--",
            linewidth=1.0,
            label="Baseline lịch sử",
        )
    ax.set_title(f"{ne_id} / {cell_id} — {kpi_name}", fontsize=10, fontweight="bold")
    ax.set_xlabel("Thời gian")
    ax.set_ylabel("Giá trị KPI")
    ax.grid(True, alpha=0.25)
    handles, _ = ax.get_legend_handles_labels()
    if handles:
        ax.legend(fontsize=7, frameon=False)
    fig.autofmt_xdate(rotation=25)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _knowledge_rows(
    analysis: pd.DataFrame,
    knowledge_base: KnowledgeBaseService | None,
) -> pd.DataFrame:
    enriched = enrich_kpi_changes_with_knowledge(analysis, knowledge_base)
    cols = [
        "kpi_name",
        "change_direction",
        "knowledge_status",
        "knowledge_version",
        "knowledge_meaning",
        "knowledge_source",
    ]
    for column in cols:
        if column not in enriched.columns:
            enriched[column] = ""
    return enriched[cols].drop_duplicates().reset_index(drop=True)


def _approved_patterns(
    analysis: pd.DataFrame,
    knowledge_base: KnowledgeBaseService | None,
    *,
    impact_type: str,
) -> tuple[dict[str, Any], ...]:
    if knowledge_base is None or analysis.empty:
        return tuple()
    patterns: dict[str, dict[str, Any]] = {}
    for kpi_name in sorted(set(analysis["kpi_name"].astype(str))):
        directions = set(
            analysis.loc[analysis["kpi_name"].astype(str) == kpi_name, "change_direction"]
            .fillna("")
            .astype(str)
            .str.upper()
        ) if "change_direction" in analysis.columns else set()
        for row in knowledge_base.approved_patterns_for_kpi(kpi_name):
            if str(row.get("impact_type", "")) != str(impact_type):
                continue
            pattern_direction = str(row.get("change_direction", "")).upper()
            if pattern_direction and directions and pattern_direction not in directions:
                continue
            patterns[str(row.get("pattern_id"))] = row
    return tuple(patterns[key] for key in sorted(patterns))


def _executive_summary(analysis: pd.DataFrame) -> tuple[tuple[str, ...], str]:
    if analysis.empty:
        return ("Không có KPI đủ điều kiện phân tích cho tác động này.",), "Không đủ dữ liệu để kết luận tổng thể."

    kpi_count = int(analysis["kpi_name"].astype(str).nunique())
    anomaly_count = int(analysis.loc[analysis["anomaly_flag"].fillna(False).astype(bool), "kpi_name"].astype(str).nunique())
    assessment = analysis["change_assessment"].fillna("NO_CHANGE").astype(str)
    degraded = int(analysis.loc[assessment.eq("DEGRADED"), "kpi_name"].astype(str).nunique())
    improved = int(analysis.loc[assessment.eq("IMPROVED"), "kpi_name"].astype(str).nunique())
    changed = int(analysis.loc[~assessment.eq("NO_CHANGE"), "kpi_name"].astype(str).nunique())
    lines = (
        f"Đã phân tích {kpi_count} KPI; {changed} KPI có thay đổi được ghi nhận.",
        f"Có {anomaly_count} KPI bị gắn cờ bất thường sau tác động.",
        f"Đánh giá chiều tác động: {degraded} KPI suy giảm, {improved} KPI cải thiện.",
    )
    if degraded > 0 or anomaly_count > 0:
        conclusion = (
            f"Tác động cần được xem xét: {degraded} KPI suy giảm và "
            f"{anomaly_count} KPI có cờ bất thường."
        )
    elif improved > 0:
        conclusion = f"Không ghi nhận KPI suy giảm; {improved} KPI được đánh giá cải thiện."
    else:
        conclusion = "Không ghi nhận thay đổi có ý nghĩa trên các KPI đủ điều kiện phân tích."
    return lines, conclusion


def build_impact_report_model(
    clean_df: pd.DataFrame,
    impact: ImpactEvent,
    analysis_result: pd.DataFrame,
    *,
    knowledge_base: KnowledgeBaseService | None = None,
) -> ImpactReportModel:
    """Build the FR-601 report model from existing core outputs."""

    analysis = _normalize_analysis(analysis_result)
    knowledge = _knowledge_rows(analysis, knowledge_base)
    patterns = _approved_patterns(
        analysis, knowledge_base, impact_type=str(impact.impact_type)
    )
    charts = tuple(
        (
            f"{ne_id} / {cell_id} — {kpi_name}",
            _impact_chart(clean_df, impact, analysis, ne_id, cell_id, kpi_name),
        )
        for ne_id, cell_id, kpi_name in _affected_keys(analysis)
    )
    executive, conclusion = _executive_summary(analysis)
    return ImpactReportModel(
        impact=impact,
        analysis=analysis,
        knowledge_rows=knowledge,
        approved_patterns=patterns,
        charts=charts,
        executive_summary=executive,
        overall_conclusion=conclusion,
    )


def _impact_info_rows(impact: ImpactEvent) -> list[tuple[str, str]]:
    return [
        ("Impact ID", str(impact.impact_id)),
        ("NE", str(impact.ne_id)),
        ("Cell", str(impact.cell_id or "Toàn NE")),
        ("Thời gian bắt đầu", str(impact.t1_utc)),
        ("Thời gian kết thúc", str(impact.t2_utc or "ongoing")),
        ("Loại tác động", str(impact.impact_type)),
        ("Operator", str(impact.operator)),
        ("Nguồn", str(impact.source)),
        ("Mô tả", str(impact.description)),
    ]


def _delta_columns(frame: pd.DataFrame) -> list[str]:
    preferred = [
        "ne_id",
        "cell_id",
        "kpi_name",
        "temporal_profile",
        "day_type",
        "pre_mean",
        "post_mean",
        "delta_abs",
        "delta_percent",
        "welch_t_p_value",
        "mann_whitney_p_value",
        "change_assessment",
        "anomaly_flag",
        "anomaly_source",
    ]
    return [column for column in preferred if column in frame.columns]


def generate_impact_report_html(model: ImpactReportModel, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    impact_rows = "".join(
        f"<tr><th>{escape(label)}</th><td>{escape(value)}</td></tr>"
        for label, value in _impact_info_rows(model.impact)
    )
    delta = model.analysis[_delta_columns(model.analysis)].copy()
    delta_html = delta.to_html(index=False, escape=True, border=0, classes="data-table")
    kb_html = model.knowledge_rows.to_html(index=False, escape=True, border=0, classes="data-table")
    pattern_html = (
        "<p>Chưa có pattern đã được phê duyệt phù hợp với các KPI trong báo cáo.</p>"
        if not model.approved_patterns
        else "<ul>" + "".join(
            f"<li>{escape(str(row.get('summary', '')))}</li>" for row in model.approved_patterns
        ) + "</ul>"
    )
    charts_html = "".join(
        f"<figure><figcaption>{escape(label)}</figcaption>"
        f"<img src='data:image/png;base64,{base64.b64encode(png).decode('ascii')}' alt='{escape(label)}'></figure>"
        for label, png in model.charts
    ) or "<p>Không có KPI bị ảnh hưởng cần vẽ biểu đồ.</p>"
    summary_html = "".join(f"<li>{escape(line)}</li>" for line in model.executive_summary)
    html = f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Báo cáo đánh giá hệ quả tác động</title>
<style>
body{{font-family:Arial,sans-serif;margin:0;background:#f8fafc;color:#0f172a;line-height:1.45}}
main{{max-width:1180px;margin:auto;padding:24px}}section{{background:white;padding:20px;margin:16px 0;border-radius:10px}}
h1,h2{{margin-top:0}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{border:1px solid #cbd5e1;padding:7px;text-align:left;vertical-align:top}}th{{background:#f1f5f9}}
.data-table{{display:block;overflow-x:auto}}figure{{margin:18px 0}}figcaption{{font-weight:700;margin-bottom:8px}}img{{max-width:100%;height:auto}}
.conclusion{{font-weight:700}}
@media(max-width:700px){{main{{padding:10px}}section{{padding:12px}}table{{font-size:11px}}}}
</style></head><body><main>
<h1>Báo cáo đánh giá hệ quả tác động</h1>
<section><h2>1. Tóm tắt điều hành</h2><ul>{summary_html}</ul><p class="conclusion">{escape(model.overall_conclusion)}</p></section>
<section><h2>2. Thông tin tác động</h2><table>{impact_rows}</table></section>
<section><h2>3. Bảng KPI trước/sau tác động</h2>{delta_html}</section>
<section><h2>4. Biểu đồ KPI bị ảnh hưởng</h2>{charts_html}</section>
<section><h2>5. Giải thích từ Knowledge Base</h2>{kb_html}<h3>Pattern đã được phê duyệt</h3>{pattern_html}</section>
<section><h2>6. Kết luận tổng thể</h2><p class="conclusion">{escape(model.overall_conclusion)}</p></section>
</main></body></html>"""
    path.write_text(html, encoding="utf-8")
    return path


def _pdf_text_page(pdf: PdfPages, title: str, lines: list[str]) -> None:
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.text(0.07, 0.95, title, fontsize=16, fontweight="bold", va="top")
    y = 0.90
    for line in lines:
        wrapped = textwrap.wrap(str(line), width=105) or [""]
        for part in wrapped:
            fig.text(0.07, y, part, fontsize=9, va="top")
            y -= 0.022
            if y < 0.06:
                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)
                fig = plt.figure(figsize=(8.27, 11.69))
                y = 0.95
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def _pdf_table(pdf: PdfPages, title: str, frame: pd.DataFrame) -> None:
    if frame.empty:
        _pdf_text_page(pdf, title, ["Không có dữ liệu."])
        return
    page_size = 22
    for start in range(0, len(frame), page_size):
        page = frame.iloc[start : start + page_size].copy()
        page = page.map(lambda value: _fmt(value) if isinstance(value, (float, np.floating)) else str(value))
        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        ax.axis("off")
        ax.set_title(title, loc="left", fontsize=13, fontweight="bold", pad=12)
        table = ax.table(cellText=page.values, colLabels=page.columns, loc="upper left", cellLoc="left")
        table.auto_set_font_size(False)
        table.set_fontsize(6.5)
        table.scale(1, 1.25)
        fig.tight_layout()
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)


def generate_impact_report_pdf(model: ImpactReportModel, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(path) as pdf:
        _pdf_text_page(
            pdf,
            "Báo cáo đánh giá hệ quả tác động",
            [*model.executive_summary, "", model.overall_conclusion, ""]
            + [f"{label}: {value}" for label, value in _impact_info_rows(model.impact)],
        )
        _pdf_table(pdf, "Bảng KPI trước/sau tác động", model.analysis[_delta_columns(model.analysis)])
        for label, png in model.charts:
            fig = plt.figure(figsize=(11.69, 8.27))
            fig.text(0.06, 0.95, label, fontsize=13, fontweight="bold", va="top")
            image = plt.imread(io.BytesIO(png), format="png")
            ax = fig.add_axes([0.06, 0.10, 0.88, 0.78])
            ax.imshow(image)
            ax.axis("off")
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
        _pdf_table(pdf, "Giải thích từ Knowledge Base", model.knowledge_rows)
        pattern_lines = [str(row.get("summary", "")) for row in model.approved_patterns]
        _pdf_text_page(
            pdf,
            "Pattern đã được phê duyệt và kết luận tổng thể",
            (pattern_lines or ["Chưa có pattern đã được phê duyệt phù hợp."])
            + ["", model.overall_conclusion],
        )
    return path


def generate_impact_report_excel(model: ImpactReportModel, output_path: str | Path) -> Path:
    """Generate FR-601 Excel report including affected-KPI chart images."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = pd.DataFrame(
        {"Tóm tắt điều hành": [*model.executive_summary, model.overall_conclusion]}
    )
    impact_info = pd.DataFrame(_impact_info_rows(model.impact), columns=["Trường", "Giá trị"])
    patterns = pd.DataFrame(list(model.approved_patterns))
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        impact_info.to_excel(writer, sheet_name="Impact", index=False)
        model.analysis[_delta_columns(model.analysis)].to_excel(writer, sheet_name="KPI Delta", index=False)
        model.knowledge_rows.to_excel(writer, sheet_name="Knowledge", index=False)
        if patterns.empty:
            pd.DataFrame({"Pattern": ["Chưa có pattern đã được phê duyệt phù hợp."]}).to_excel(
                writer, sheet_name="Patterns", index=False
            )
        else:
            patterns.to_excel(writer, sheet_name="Patterns", index=False)

        if model.charts:
            from openpyxl.drawing.image import Image as XLImage

            worksheet = writer.book.create_sheet("Charts")
            image_buffers: list[io.BytesIO] = []
            row = 1
            for label, png in model.charts:
                worksheet.cell(row=row, column=1, value=label)
                buffer = io.BytesIO(png)
                image_buffers.append(buffer)
                image = XLImage(buffer)
                image.width = 720
                image.height = 272
                worksheet.add_image(image, f"A{row + 1}")
                row += 18
            # image_buffers remains alive until the writer context serializes the workbook.
            _ = image_buffers
    return path


def generate_impact_report(
    model: ImpactReportModel,
    output_path: str | Path,
) -> Path:
    """Render FR-601 based on the output file suffix."""

    suffix = Path(output_path).suffix.lower()
    if suffix == ".html":
        return generate_impact_report_html(model, output_path)
    if suffix == ".pdf":
        return generate_impact_report_pdf(model, output_path)
    if suffix in {".xlsx", ".xlsm"}:
        return generate_impact_report_excel(model, output_path)
    raise ValueError("FR-601 chỉ hỗ trợ HTML, PDF hoặc Excel (.xlsx/.xlsm)")


__all__ = [
    "ImpactReportModel",
    "build_impact_report_model",
    "generate_impact_report",
    "generate_impact_report_excel",
    "generate_impact_report_html",
    "generate_impact_report_pdf",
]
