"""Daily/weekly network-health reports built from existing RKAA analysis artifacts.

The report is deliberately user-facing: internal requirement IDs are never rendered.
Daily periods follow the configured daily-cycle semantics used by the temporal analysis:
current 24h plus cumulative historical daily references 24-72h, 24-144h and 24-288h.
Weekly periods follow current 7 days versus the immediately preceding 7 days.
"""

from __future__ import annotations

import base64
import io
import textwrap
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

from rkaa.domain.knowledge_base import KnowledgeStore


_REQUIRED_INPUT = {"timestamp", "ne_id", "cell_id", "kpi_name", "value"}

# Báo cáo vận hành chỉ xét đúng 7 KPI chính đã chốt cho RKAA.
FOCUS7_KPIS = (
    "ENDC SSR VTNET IniAtt (%)",
    "ENDC CDR VTNET (%)",
    "NR RASR VTNET (%)",
    "PSCell Change Intra-SgNB SR VTNET (%)",
    "PSCell Change Inter-SgNB SR VTNET (%)",
    "Max RRC Connected NR ENDC User (UE)",
    "NSA PS Traffic (GBytes)",
)

_DAILY_REFERENCE_ENDPOINTS_HOURS = (72, 144, 288)
_WEEK_DAYS = 7
_TOP_PAIR_LIMIT = 5

# Daily temporal-profile windows follow the current FR-401 semantics.
_DAILY_PROFILE_WINDOWS = {
    "BUSY": ((7.0, 21.0),),
    "TRANSITION": ((6.0, 7.0), (21.0, 22.0)),
    "OFF_PEAK": ((0.0, 6.0), (22.0, 24.0)),
}

_ANOMALY_COLORS = {
    "BUSY": "#ef4444",
    "TRANSITION": "#f59e0b",
    "OFF_PEAK": "#3b82f6",
}
_ANOMALY_SHADE_ALPHA = 0.24


@dataclass(frozen=True, slots=True)
class ReferencePeriod:
    label: str
    start: pd.Timestamp
    end: pd.Timestamp
    aggregation: str


@dataclass(frozen=True, slots=True)
class HealthPeriod:
    kind: str
    label: str
    start: pd.Timestamp
    end: pd.Timestamp
    selection_note: str
    references: tuple[ReferencePeriod, ...] = field(default_factory=tuple)
    distinctive_score: float | None = None


@dataclass(frozen=True, slots=True)
class HealthReportArtifacts:
    # Field names remain backward compatible with earlier runner versions.
    fr401_comparison: Path | None = None
    fr402_comparison: Path | None = None
    trend_summary: Path | None = None
    fr404_summary: Path | None = None
    change_points: Path | None = None
    knowledge_store: Path | None = None


@dataclass(frozen=True, slots=True)
class ReportModel:
    period: HealthPeriod
    current: pd.DataFrame
    kpi_summary: pd.DataFrame
    hierarchy_summary: pd.DataFrame
    degrading_ne: pd.DataFrame
    anomaly_details: pd.DataFrame
    metadata: dict[str, Any]
    detection: dict[str, Any]
    trend: dict[str, Any]
    approved_kb: list[dict[str, Any]]
    pending_zero_variance: list[dict[str, Any]]
    period_chart: bytes | None
    charts: tuple[tuple[str, bytes], ...]
    anomaly_chart_pairs: tuple[dict[str, Any], ...]
    executive_summary: tuple[str, ...]
    overall_conclusion: tuple[str, ...]


def prepare_health_input(df: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(_REQUIRED_INPUT.difference(df.columns))
    if missing:
        raise ValueError(f"Báo cáo thiếu cột input: {', '.join(missing)}")
    working = df.copy()
    working["timestamp"] = pd.to_datetime(
        working["timestamp"], errors="coerce", utc=True, format="mixed"
    )
    working["value"] = pd.to_numeric(working["value"], errors="coerce")
    working = working.dropna(subset=["timestamp", "value"])
    if "is_counter" in working.columns:
        raw = working["is_counter"]
        if pd.api.types.is_bool_dtype(raw.dtype):
            is_counter = raw.fillna(False)
        else:
            is_counter = raw.astype("string").str.lower().isin({"1", "true", "yes", "y"})
        working = working.loc[~is_counter].copy()

    # Health report authority: chỉ 7 KPI chính; các KPI phụ không tham gia
    # xếp hạng NE-Cell, anomaly count, bảng chi tiết hay biểu đồ.
    working = working[working["kpi_name"].astype(str).isin(FOCUS7_KPIS)].copy()
    return working.sort_values("timestamp").reset_index(drop=True)


def _daily_references(anchor_end: pd.Timestamp) -> tuple[ReferencePeriod, ...]:
    current_start = anchor_end - pd.Timedelta(hours=24)
    return tuple(
        ReferencePeriod(
            label=f"Trung bình chu kỳ ngày trong 24-{endpoint} giờ trước",
            start=anchor_end - pd.Timedelta(hours=endpoint),
            end=current_start,
            aggregation="mean_daily_cycle",
        )
        for endpoint in _DAILY_REFERENCE_ENDPOINTS_HOURS
    )


def select_health_period(df: pd.DataFrame, kind: str) -> HealthPeriod:
    if df.empty:
        raise ValueError("Không có dữ liệu để chọn kỳ báo cáo")
    anchor = df["timestamp"].max()
    kind = kind.strip().lower()

    if kind == "last-day":
        start = anchor - pd.Timedelta(hours=24)
        return HealthPeriod(
            kind=kind,
            label="Chu kỳ 24 giờ gần nhất",
            start=start,
            end=anchor,
            selection_note=(
                "Chu kỳ hiện tại dài 24 giờ; đối chiếu với ba chu kỳ ngày trung bình "
                "từ các khoảng 24-72, 24-144 và 24-288 giờ trước."
            ),
            references=_daily_references(anchor),
        )

    if kind == "last-week":
        start = anchor - pd.Timedelta(days=_WEEK_DAYS)
        previous = ReferencePeriod(
            label="Tuần liền trước",
            start=anchor - pd.Timedelta(days=2 * _WEEK_DAYS),
            end=start,
            aggregation="direct_window",
        )
        return HealthPeriod(
            kind=kind,
            label="Chu kỳ 7 ngày gần nhất",
            start=start,
            end=anchor,
            selection_note="Chu kỳ tuần hiện tại được đối chiếu với đúng 7 ngày liền trước.",
            references=(previous,),
        )

    if kind != "distinctive-day":
        raise ValueError("period phải là last-day, distinctive-day hoặc last-week")

    day, score = select_distinctive_day(df)
    selected = df[df["timestamp"].dt.strftime("%Y-%m-%d") == day]
    if selected.empty:
        raise ValueError("Không tìm thấy dữ liệu của ngày đặc trưng đã chọn")
    # Use the actual last sample of that calendar day as anchor so the same
    # open-left/closed-right 24h convention yields exactly that day's samples.
    end = selected["timestamp"].max()
    start = end - pd.Timedelta(hours=24)
    return HealthPeriod(
        kind=kind,
        label=f"Chu kỳ ngày đặc trưng {day}",
        start=start,
        end=end,
        selection_note=(
            "Ngày được chọn tự động trong các ngày đủ dữ liệu theo robust deviation; "
            "chu kỳ 24 giờ của ngày này dùng cùng ba khoảng tham chiếu 24-72, 24-144 "
            "và 24-288 giờ trước."
        ),
        references=_daily_references(end),
        distinctive_score=float(score),
    )


def select_distinctive_day(df: pd.DataFrame) -> tuple[str, float]:
    """Pick the most globally distinctive complete calendar day deterministically."""

    working = df.copy()
    working["day"] = working["timestamp"].dt.strftime("%Y-%m-%d")
    rows_per_day = working.groupby("day").size()
    if rows_per_day.empty:
        raise ValueError("Không có ngày hợp lệ")
    completeness_floor = float(rows_per_day.max()) * 0.90
    complete_days = set(rows_per_day[rows_per_day >= completeness_floor].index)
    working = working[working["day"].isin(complete_days)]

    keys = ["ne_id", "cell_id", "kpi_name"]
    daily = (
        working.groupby([*keys, "day"], dropna=False, sort=False)["value"]
        .mean()
        .rename("daily_mean")
        .reset_index()
    )
    grouped = daily.groupby(keys, dropna=False, sort=False)["daily_mean"]
    daily["series_median"] = grouped.transform("median")
    daily["abs_dev"] = (daily["daily_mean"] - daily["series_median"]).abs()
    daily["mad"] = daily.groupby(keys, dropna=False, sort=False)["abs_dev"].transform("median")
    denom = 1.4826 * daily["mad"]
    fallback_scale = np.maximum(daily["series_median"].abs() * 0.01, 1e-6)
    daily["robust_deviation"] = np.where(
        denom > 1e-12,
        daily["abs_dev"] / denom,
        np.where(daily["abs_dev"] > 1e-12, daily["abs_dev"] / fallback_scale, 0.0),
    )
    daily["robust_deviation"] = np.clip(daily["robust_deviation"], 0, 20)
    scores = daily.groupby("day")["robust_deviation"].mean().sort_values(ascending=False)
    if scores.empty:
        raise ValueError("Không tính được distinctive-day score")
    return str(scores.index[0]), float(scores.iloc[0])


def _period_slice(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    # Match temporal-analysis semantics: open-left, closed-right.
    return df[(df["timestamp"] > start) & (df["timestamp"] <= end)].copy()


def _stats(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["kpi_name"])
    grouped = frame.groupby("kpi_name", dropna=False)["value"]
    result = grouped.agg(["count", "mean", "median", "std"]).reset_index()
    result[f"{prefix}_p05"] = grouped.quantile(0.05).to_numpy()
    result[f"{prefix}_p95"] = grouped.quantile(0.95).to_numpy()
    return result.rename(
        columns={
            "count": f"{prefix}_count",
            "mean": f"{prefix}_mean",
            "median": f"{prefix}_median",
            "std": f"{prefix}_std",
        }
    )


def _mean_daily_cycle(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    working = frame.copy()
    working["minute_of_day"] = working["timestamp"].dt.hour * 60 + working["timestamp"].dt.minute
    keys = ["kpi_name", "minute_of_day"]
    if "unit" in working.columns:
        keys.append("unit")
    return (
        working.groupby(keys, dropna=False, sort=True)["value"]
        .mean()
        .rename("value")
        .reset_index()
    )


def _period_summary(df: pd.DataFrame, period: HealthPeriod) -> tuple[pd.DataFrame, pd.DataFrame]:
    current = _period_slice(df, period.start, period.end)
    current_stats = _stats(current, "current")
    rows: list[pd.DataFrame] = []

    for reference in period.references:
        source = _period_slice(df, reference.start, reference.end)
        if reference.aggregation == "mean_daily_cycle":
            source = _mean_daily_cycle(source)
        reference_stats = _stats(source, "reference")
        merged = current_stats.merge(reference_stats, how="outer", on="kpi_name")
        merged["reference_label"] = reference.label
        merged["reference_start"] = reference.start
        merged["reference_end"] = reference.end
        merged["delta_abs"] = merged["current_mean"] - merged["reference_mean"]
        merged["delta_percent"] = np.where(
            merged["reference_mean"].abs() > 1e-12,
            merged["delta_abs"] / merged["reference_mean"].abs() * 100.0,
            np.nan,
        )
        merged["abs_delta_percent"] = merged["delta_percent"].abs()
        rows.append(merged)

    if not rows:
        summary = current_stats.copy()
        summary["reference_label"] = "Không có kỳ tham chiếu"
        summary["reference_mean"] = np.nan
        summary["delta_abs"] = np.nan
        summary["delta_percent"] = np.nan
        summary["abs_delta_percent"] = np.nan
    else:
        summary = pd.concat(rows, ignore_index=True)
    summary = summary.sort_values("abs_delta_percent", ascending=False, na_position="last")
    return current, summary


def _read_optional(path: Path | None) -> pd.DataFrame:
    if path is None or not path.exists():
        return pd.DataFrame()
    if path.suffix.lower() in {".pkl", ".pickle"}:
        return pd.read_pickle(path)
    return pd.read_csv(path)


def _timestamps_match(value: Any, target: pd.Timestamp, tolerance: pd.Timedelta) -> bool:
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return False
    return abs(parsed - target) <= tolerance


def _pair_anomaly_views(aligned: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rank NE-Cell pairs and materialize all 7 KPI rows for the top pairs.

    Ranking authority is the number of *distinct focus KPI* with at least one
    anomaly flag in the reporting period (0..7). This avoids inflating the
    ranking merely because one KPI is evaluated in many temporal profiles or
    reference windows. ``anomaly_instances`` is retained as a secondary signal.
    """

    if aligned.empty:
        return pd.DataFrame(), pd.DataFrame()

    work = aligned[aligned["kpi_name"].astype(str).isin(FOCUS7_KPIS)].copy()
    if work.empty:
        return pd.DataFrame(), pd.DataFrame()

    work["_anomaly"] = work.get(
        "anomaly_flag", pd.Series(False, index=work.index)
    ).fillna(False).astype(bool)
    work["_delta_percent"] = pd.to_numeric(
        work.get("delta_percent", pd.Series(np.nan, index=work.index)),
        errors="coerce",
    )
    work["_abs_delta_percent"] = work["_delta_percent"].abs()

    ranking_rows: list[dict[str, Any]] = []
    for (ne_id, cell_id), group in work.groupby(["ne_id", "cell_id"], dropna=False, sort=False):
        anomalous = group[group["_anomaly"]]
        if anomalous.empty:
            continue
        ranking_rows.append(
            {
                "ne_id": ne_id,
                "cell_id": cell_id,
                "anomalous_kpi_count": int(anomalous["kpi_name"].nunique()),
                "anomaly_instances": int(anomalous["_anomaly"].sum()),
                "max_abs_delta_percent": float(group["_abs_delta_percent"].max())
                if group["_abs_delta_percent"].notna().any()
                else np.nan,
            }
        )

    ranking = pd.DataFrame(ranking_rows)
    if ranking.empty:
        return ranking, pd.DataFrame()
    ranking = (
        ranking.sort_values(
            ["anomalous_kpi_count", "anomaly_instances", "max_abs_delta_percent", "ne_id", "cell_id"],
            ascending=[False, False, False, True, True],
            na_position="last",
        )
        .head(_TOP_PAIR_LIMIT)
        .reset_index(drop=True)
    )
    ranking.insert(0, "rank", np.arange(1, len(ranking) + 1))

    detail_rows: list[dict[str, Any]] = []
    for pair in ranking.itertuples(index=False):
        pair_frame = work[
            (work["ne_id"].astype(str) == str(pair.ne_id))
            & (work["cell_id"].astype(str) == str(pair.cell_id))
        ]
        for kpi in FOCUS7_KPIS:
            subset = pair_frame[pair_frame["kpi_name"].astype(str) == kpi].copy()
            anomaly_subset = subset[subset["_anomaly"]]
            candidate = anomaly_subset if not anomaly_subset.empty else subset

            if candidate.empty:
                detail_rows.append(
                    {
                        "rank": pair.rank,
                        "ne_id": pair.ne_id,
                        "cell_id": pair.cell_id,
                        "kpi_name": kpi,
                        "anomaly_flag": False,
                        "anomaly_instances": 0,
                        "current_mean": np.nan,
                        "reference_mean": np.nan,
                        "delta_percent": np.nan,
                        "comparison_context": "Không có dữ liệu so sánh",
                        "decision_source": "-",
                    }
                )
                continue

            # Một KPI có thể có nhiều profile/reference. Dòng đại diện là dòng
            # bất thường có |delta%| lớn nhất; nếu KPI bình thường thì lấy dòng
            # có |delta%| lớn nhất để vẫn hiển thị đủ 7 KPI.
            if candidate["_abs_delta_percent"].notna().any():
                representative = candidate.loc[candidate["_abs_delta_percent"].idxmax()]
            else:
                representative = candidate.iloc[0]

            context_parts = []
            for column in ("temporal_profile", "reference_label", "group_scope", "group_value"):
                value = representative.get(column)
                if pd.notna(value) and str(value).strip():
                    context_parts.append(str(value))

            detail_rows.append(
                {
                    "rank": pair.rank,
                    "ne_id": pair.ne_id,
                    "cell_id": pair.cell_id,
                    "kpi_name": kpi,
                    "anomaly_flag": bool(subset["_anomaly"].any()),
                    "anomaly_instances": int(subset["_anomaly"].sum()),
                    "current_mean": pd.to_numeric(
                        pd.Series([representative.get("current_mean")]), errors="coerce"
                    ).iloc[0],
                    "reference_mean": pd.to_numeric(
                        pd.Series([representative.get("reference_mean")]), errors="coerce"
                    ).iloc[0],
                    "delta_percent": representative.get("_delta_percent", np.nan),
                    "comparison_context": " / ".join(context_parts) or "-",
                    "decision_source": str(representative.get("anomaly_decision_source", "-")),
                }
            )

    return ranking, pd.DataFrame(detail_rows)


def _aligned_detection_snapshot(
    artifacts: HealthReportArtifacts,
    period: HealthPeriod,
) -> dict[str, Any]:
    if period.kind == "last-week":
        frame = _read_optional(artifacts.fr402_comparison)
        label = "So sánh tuần hiện tại với tuần liền trước"
    else:
        frame = _read_optional(artifacts.fr401_comparison)
        label = "So sánh chu kỳ ngày hiện tại với lịch sử"

    if frame.empty:
        return {"available": False, "aligned": False, "label": label}

    # Artifact có thể chứa KPI phụ; báo cáo chỉ xét đúng focus7.
    frame = frame[frame["kpi_name"].astype(str).isin(FOCUS7_KPIS)].copy()
    aligned = frame
    if "current_end" in frame.columns:
        tolerance = pd.Timedelta(minutes=1)
        mask = frame["current_end"].map(lambda value: _timestamps_match(value, period.end, tolerance))
        aligned = frame.loc[mask].copy()
    if aligned.empty:
        return {
            "available": True,
            "aligned": False,
            "label": label,
            "rows": int(len(frame)),
            "anomalies": 0,
            "anomalous_pair_count": 0,
            "anomalous_pair_kpi_count": 0,
            "top_pairs": pd.DataFrame(),
            "top_pair_kpis": pd.DataFrame(),
        }

    anomaly = aligned.get("anomaly_flag", pd.Series(False, index=aligned.index)).fillna(False).astype(bool)
    sigma_applicable = aligned.get(
        "sigma_applicable", pd.Series(True, index=aligned.index)
    ).fillna(False).astype(bool)
    top_pairs, top_pair_kpis = _pair_anomaly_views(aligned)
    anomalous_rows = aligned.loc[anomaly]
    return {
        "available": True,
        "aligned": True,
        "label": label,
        "rows": int(len(aligned)),
        # Số instance vẫn được báo cáo, nhưng ranking không dùng trực tiếp số này.
        "anomalies": int(anomaly.sum()),
        "anomalous_pair_count": int(
            anomalous_rows[["ne_id", "cell_id"]].drop_duplicates().shape[0]
        ),
        "anomalous_pair_kpi_count": int(
            anomalous_rows[["ne_id", "cell_id", "kpi_name"]].drop_duplicates().shape[0]
        ),
        "sigma_not_applicable": int((~sigma_applicable).sum()),
        "top_pairs": top_pairs,
        "top_pair_kpis": top_pair_kpis,
        "aligned_frame": aligned,
    }


def _trend_snapshot(artifacts: HealthReportArtifacts, period: HealthPeriod) -> dict[str, Any]:
    trend = _read_optional(artifacts.trend_summary)
    percent_direction = _read_optional(artifacts.fr404_summary)
    change_points = _read_optional(artifacts.change_points)

    # Mọi thành phần báo cáo đều cùng scope focus7.
    for frame in (trend, percent_direction, change_points):
        if not frame.empty and "kpi_name" in frame.columns:
            frame.drop(
                frame.index[~frame["kpi_name"].astype(str).isin(FOCUS7_KPIS)],
                inplace=True,
            )

    if not change_points.empty and "change_timestamp" in change_points.columns:
        change_points = change_points.copy()
        change_points["change_timestamp"] = pd.to_datetime(
            change_points["change_timestamp"], errors="coerce", utc=True, format="mixed"
        )
        change_points = change_points[
            (change_points["change_timestamp"] > period.start)
            & (change_points["change_timestamp"] <= period.end)
        ].copy()
    return {
        "trend": trend,
        "percent_direction": percent_direction,
        "change_points": change_points,
    }



def _hierarchy_kpi_summary(current: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the seven focus KPI by NE only."""

    columns = ["level", "entity", "kpi_name", "count", "mean", "p05", "p95"]
    if current.empty:
        return pd.DataFrame(columns=columns)

    grouped = current.groupby(["ne_id", "kpi_name"], dropna=False, sort=True)["value"]
    frame = grouped.agg(["count", "mean"]).reset_index()
    frame["p05"] = grouped.quantile(0.05).to_numpy()
    frame["p95"] = grouped.quantile(0.95).to_numpy()
    frame.insert(0, "level", "NE")
    frame = frame.rename(columns={"ne_id": "entity"})
    return frame[columns].sort_values(["entity", "kpi_name"], kind="stable").reset_index(drop=True)


def _degrading_ne_summary(trend_frame: pd.DataFrame) -> pd.DataFrame:
    columns = ["ne_id", "degrading_kpi_count", "affected_cell_count", "degrading_series_count", "kpis"]
    if trend_frame.empty or "trend_label" not in trend_frame.columns or "ne_id" not in trend_frame.columns:
        return pd.DataFrame(columns=columns)
    work = trend_frame[trend_frame["kpi_name"].astype(str).isin(FOCUS7_KPIS)].copy()
    work = work[work["trend_label"].astype(str).str.lower() == "degrading"]
    if work.empty:
        return pd.DataFrame(columns=columns)
    rows = []
    for ne_id, group in work.groupby("ne_id", dropna=False, sort=True):
        rows.append(
            {
                "ne_id": ne_id,
                "degrading_kpi_count": int(group["kpi_name"].nunique()),
                "affected_cell_count": int(group["cell_id"].nunique()) if "cell_id" in group.columns else 0,
                "degrading_series_count": int(len(group)),
                "kpis": ", ".join(sorted(group["kpi_name"].astype(str).unique())),
            }
        )
    return pd.DataFrame(rows, columns=columns).sort_values(
        ["degrading_kpi_count", "degrading_series_count", "ne_id"], ascending=[False, False, True]
    ).reset_index(drop=True)


def _friendly_reference(row: pd.Series, period: HealthPeriod) -> str:
    label = str(row.get("reference_label", "")).strip()
    daily_labels = {
        "24H_TO_72H_AVG": "trung bình chu kỳ ngày trong khoảng 24-72 giờ trước",
        "24H_TO_144H_AVG": "trung bình chu kỳ ngày trong khoảng 24-144 giờ trước",
        "24H_TO_288H_AVG": "trung bình chu kỳ ngày trong khoảng 24-288 giờ trước",
    }
    if label in daily_labels:
        basis = daily_labels[label]
    elif label == "PREVIOUS_WEEK":
        basis = "tuần liền trước"
    else:
        basis = label or "baseline tham chiếu"

    context: list[str] = []
    profile = str(row.get("temporal_profile", "")).strip()
    if profile and profile.lower() != "nan":
        context.append(profile)
    scope = str(row.get("group_scope", "")).strip()
    group_value = str(row.get("group_value", "")).strip()
    if scope and scope.lower() != "nan" and group_value and group_value.lower() != "nan":
        if scope == "DAY_TYPE":
            translated = {"WEEKDAY": "ngày thường", "WEEKEND": "cuối tuần"}.get(group_value, group_value)
            context.append(translated)
        elif scope == "DAY_OF_WEEK":
            context.append(group_value.title())
        else:
            context.append(group_value)
    return basis + (" - " + " / ".join(context) if context else "")


def _detection_reason(row: pd.Series) -> str:
    source = str(row.get("anomaly_decision_source", row.get("anomaly_source", ""))).strip()
    if source == "FR303_THRESHOLD" or bool(row.get("anomaly_threshold", False)):
        severity = str(row.get("threshold_severity", "WARNING")).strip()
        direction = str(row.get("threshold_direction", "")).strip()
        mode = str(row.get("threshold_mode", "")).strip()
        value = pd.to_numeric(pd.Series([row.get("threshold_value")]), errors="coerce").iloc[0]
        threshold_text = _fmt(value, 3) if pd.notna(value) else "ngưỡng đã cấu hình"
        return f"Vượt ngưỡng vận hành {severity}: {direction} / {mode}, ngưỡng {threshold_text}."

    if bool(row.get("anomaly_3sigma", False)):
        z = pd.to_numeric(pd.Series([row.get("reference_z_score")]), errors="coerce").iloc[0]
        if pd.notna(z) and np.isfinite(z):
            return f"Độ lệch so với baseline đạt |z|={abs(float(z)):.2f}, vượt quy tắc 3-sigma."
        return "Bị gắn cờ bởi quy tắc 3-sigma so với baseline lịch sử."
    return "Bị gắn cờ bất thường bởi detector; artifact không cung cấp lý do chi tiết hơn."


def _full_anomaly_details(
    detection: dict[str, Any],
    period: HealthPeriod,
) -> pd.DataFrame:
    columns = [
        "ne_id",
        "cell_id",
        "kpi_name",
        "comparison_basis",
        "current_mean",
        "reference_mean",
        "delta_percent",
        "detection_reason",
        "temporal_profile",
        "group_scope",
        "group_value",
        "reference_label",
        "anomaly_flag",
    ]
    aligned = detection.get("aligned_frame", pd.DataFrame())
    if aligned is None or aligned.empty:
        return pd.DataFrame(columns=columns)
    anomaly = aligned.get("anomaly_flag", pd.Series(False, index=aligned.index)).fillna(False).astype(bool)
    work = aligned.loc[anomaly].copy()
    if work.empty:
        return pd.DataFrame(columns=columns)

    work["comparison_basis"] = work.apply(lambda row: _friendly_reference(row, period), axis=1)
    work["detection_reason"] = work.apply(_detection_reason, axis=1)
    for col in ("current_mean", "reference_mean", "delta_percent"):
        if col not in work.columns:
            work[col] = np.nan
    for col in ("temporal_profile", "group_scope", "group_value", "reference_label"):
        if col not in work.columns:
            work[col] = ""
    # work đã được lọc từ anomaly_flag=True. Giữ cờ này để hai biểu đồ
    # dựng lại cùng đúng vùng bất thường và cùng màu.
    work["anomaly_flag"] = True
    return work[columns].sort_values(
        ["ne_id", "cell_id", "kpi_name", "comparison_basis"], kind="stable"
    ).reset_index(drop=True)


def _knowledge_snapshot(
    artifacts: HealthReportArtifacts,
    kpis: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if artifacts.knowledge_store is None or not artifacts.knowledge_store.exists():
        return [], []
    store = KnowledgeStore(artifacts.knowledge_store)
    approved: list[dict[str, Any]] = []
    pending_zero_variance: list[dict[str, Any]] = []
    for kpi in kpis:
        record = store.latest(kpi, approved_only=True)
        if record:
            approved.append(record)
        latest_any = store.latest_any(kpi)
        if latest_any:
            for note in latest_any.get("operational_notes") or []:
                if isinstance(note, dict) and note.get("kind") == "FR302_ZERO_VARIANCE":
                    pending_zero_variance.append({"kpi_name": kpi, **note})
    return approved, pending_zero_variance


def _chart_kpis(summary: pd.DataFrame, limit: int = 4) -> list[str]:
    if summary.empty:
        return []
    ranked = (
        summary.groupby("kpi_name", dropna=False)["abs_delta_percent"]
        .max()
        .sort_values(ascending=False, na_position="last")
    )
    return [str(value) for value in ranked.head(limit).index]


def _daily_profile(frame: pd.DataFrame, kpi_name: str) -> pd.DataFrame:
    subset = frame[frame["kpi_name"].astype(str) == str(kpi_name)].copy()
    if subset.empty:
        return pd.DataFrame(columns=["hour", "value"])
    subset["minute_of_day"] = subset["timestamp"].dt.hour * 60 + subset["timestamp"].dt.minute
    return (
        subset.groupby("minute_of_day", sort=True)["value"]
        .mean()
        .rename("value")
        .reset_index()
        .assign(hour=lambda x: x["minute_of_day"] / 60.0)
    )




def _make_period_timeline_chart(period: HealthPeriod) -> bytes:
    rows = [("Kỳ hiện tại", period.start, period.end, "#2563eb")]
    for reference in period.references:
        rows.append((reference.label, reference.start, reference.end, "#94a3b8"))

    origin = min(start for _, start, _, _ in rows)
    fig, ax = plt.subplots(figsize=(8.0, 1.2 + 0.6 * len(rows)))
    for idx, (label, start, end, color) in enumerate(rows[::-1]):
        left = (start - origin).total_seconds() / 3600.0
        width = (end - start).total_seconds() / 3600.0
        ax.barh(idx, width, left=left, height=0.45, color=color, alpha=0.85)
        ax.text(left + width / 2.0, idx, label, ha="center", va="center", fontsize=8, color="white")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([row[0] for row in rows[::-1]], fontsize=8)
    tick_positions = []
    tick_labels = []
    for _, start, end, _ in rows:
        for ts in (start, end):
            pos = (ts - origin).total_seconds() / 3600.0
            tick_positions.append(pos)
            tick_labels.append(ts.strftime("%m-%d %H:%M"))
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, rotation=25, ha="right", fontsize=7)
    ax.set_xlabel("Mốc thời gian tương đối (giờ)")
    ax.set_title("Sơ đồ kỳ hiện tại và các kỳ tham chiếu", fontsize=11, fontweight="bold")
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _iter_profile_spans_for_day(day_start: pd.Timestamp, profile: str) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    windows = _DAILY_PROFILE_WINDOWS.get(str(profile).upper(), ())
    spans: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    midnight = day_start.normalize()
    for start_hour, end_hour in windows:
        start = midnight + pd.Timedelta(hours=float(start_hour))
        end = midnight + pd.Timedelta(hours=float(end_hour))
        spans.append((start, end))
    return spans


def _overlap(start: pd.Timestamp, end: pd.Timestamp, left: pd.Timestamp, right: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    s = max(start, left)
    e = min(end, right)
    if s >= e:
        return None
    return s, e


def _anomaly_spans_for_pair_kpi(detection: dict[str, Any], period: HealthPeriod, ne_id: str, cell_id: str, kpi_name: str) -> list[tuple[pd.Timestamp, pd.Timestamp, str]]:
    aligned = detection.get("aligned_frame", pd.DataFrame())
    if aligned is None or aligned.empty:
        return []
    subset = aligned[
        (aligned["ne_id"].astype(str) == str(ne_id))
        & (aligned["cell_id"].astype(str) == str(cell_id))
        & (aligned["kpi_name"].astype(str) == str(kpi_name))
        & (aligned.get("anomaly_flag", pd.Series(False, index=aligned.index)).fillna(False).astype(bool))
    ].copy()
    if subset.empty:
        return []

    spans: list[tuple[pd.Timestamp, pd.Timestamp, str]] = []
    if period.kind != "last-week":
        days = pd.date_range(period.start.normalize(), period.end.normalize(), freq="D", tz=period.start.tz)
        for row in subset.itertuples(index=False):
            profile = str(getattr(row, "temporal_profile", ""))
            for day in days:
                for span_start, span_end in _iter_profile_spans_for_day(day, profile):
                    clipped = _overlap(span_start, span_end, period.start, period.end)
                    if clipped is not None:
                        spans.append((clipped[0], clipped[1], profile))
    else:
        days = pd.date_range(period.start.normalize(), period.end.normalize(), freq="D", tz=period.start.tz)
        for row in subset.itertuples(index=False):
            profile = str(getattr(row, "temporal_profile", ""))
            scope = str(getattr(row, "group_scope", ""))
            value = str(getattr(row, "group_value", ""))
            for day in days:
                weekday_name = day.day_name().upper()
                is_weekday = day.weekday() < 5
                match = False
                if scope == "DAY_TYPE":
                    match = (value == "WEEKDAY" and is_weekday) or (value == "WEEKEND" and not is_weekday)
                elif scope == "DAY_OF_WEEK":
                    match = value == weekday_name
                if not match:
                    continue
                for span_start, span_end in _iter_profile_spans_for_day(day, profile):
                    clipped = _overlap(span_start, span_end, period.start, period.end)
                    if clipped is not None:
                        spans.append((clipped[0], clipped[1], profile))

    spans = sorted(spans, key=lambda item: item[0])
    dedup: list[tuple[pd.Timestamp, pd.Timestamp, str]] = []
    seen = set()
    for start, end, profile in spans:
        key = (start.value, end.value, profile)
        if key not in seen:
            seen.add(key)
            dedup.append((start, end, profile))
    return dedup


def _make_pair_detail_chart(df: pd.DataFrame, period: HealthPeriod, detection: dict[str, Any], ne_id: str, cell_id: str, pair_details: pd.DataFrame) -> bytes:
    pair_df = df[(df["ne_id"].astype(str) == str(ne_id)) & (df["cell_id"].astype(str) == str(cell_id))].copy()
    current = _period_slice(pair_df, period.start, period.end)
    fig, axes = plt.subplots(4, 2, figsize=(12.0, 10.5), sharex=True)
    axes = axes.flatten()
    x_end = (period.end - period.start).total_seconds() / 3600.0

    for idx, kpi in enumerate(FOCUS7_KPIS):
        ax = axes[idx]
        series = current[current["kpi_name"].astype(str) == str(kpi)].copy()
        detail_row = pair_details[pair_details["kpi_name"].astype(str) == str(kpi)]
        detail = detail_row.iloc[0] if not detail_row.empty else None
        if not series.empty:
            series["x"] = (series["timestamp"] - period.start).dt.total_seconds() / 3600.0
            ax.plot(series["x"], series["value"], linewidth=1.25, color="#1f77b4")
        if detail is not None:
            ref_mean = pd.to_numeric(pd.Series([detail.get("reference_mean")]), errors="coerce").iloc[0]
            if pd.notna(ref_mean):
                ax.axhline(float(ref_mean), linestyle="--", linewidth=0.9, color="#475569", alpha=0.85)
            for span_start, span_end, profile in _anomaly_spans_for_pair_kpi(detection, period, ne_id, cell_id, kpi):
                x0 = (span_start - period.start).total_seconds() / 3600.0
                x1 = (span_end - period.start).total_seconds() / 3600.0
                ax.axvspan(x0, x1, color=_ANOMALY_COLORS.get(profile, "#ef4444"), alpha=0.18)
        is_anomaly = bool(detail.get("anomaly_flag")) if detail is not None else False
        status = "BẤT THƯỜNG" if is_anomaly else "Bình thường"
        ax.set_title(f"{kpi} — {status}", fontsize=8.5, color="#b91c1c" if is_anomaly else "#166534")
        ax.grid(True, alpha=0.22)
        ax.set_ylabel("KPI", fontsize=7)
        ax.tick_params(labelsize=7)
        ax.set_xlim(0, x_end)

    axes[-1].axis("off")
    xlabel = "Giờ từ đầu chu kỳ ngày" if period.kind != "last-week" else "Giờ từ đầu chu kỳ tuần"
    for ax in axes[:-1]:
        ax.set_xlabel(xlabel, fontsize=7)
    fig.suptitle(f"{ne_id} / {cell_id} — đủ 7 KPI trong kỳ", fontsize=12, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()

def _make_cycle_chart(
    df: pd.DataFrame,
    period: HealthPeriod,
    ne_id: str,
    cell_id: str,
    kpi_name: str,
) -> bytes:
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    pair_df = df[
        (df["ne_id"].astype(str) == str(ne_id))
        & (df["cell_id"].astype(str) == str(cell_id))
    ].copy()
    current = _period_slice(pair_df, period.start, period.end)

    if period.kind == "last-week":
        current_kpi = current[current["kpi_name"].astype(str) == str(kpi_name)].copy()
        if not current_kpi.empty:
            current_kpi["x"] = (current_kpi["timestamp"] - period.start).dt.total_seconds() / 3600.0
            ax.plot(current_kpi["x"], current_kpi["value"], linewidth=1.2, label="Tuần hiện tại")
        reference = period.references[0]
        previous = _period_slice(pair_df, reference.start, reference.end)
        previous = previous[previous["kpi_name"].astype(str) == str(kpi_name)].copy()
        if not previous.empty:
            previous["x"] = (previous["timestamp"] - reference.start).dt.total_seconds() / 3600.0
            ax.plot(previous["x"], previous["value"], linewidth=1.2, label="Tuần liền trước")
        ax.set_xlim(0, 7 * 24)
        ax.set_xlabel("Giờ trong chu kỳ tuần")
    else:
        current_profile = _daily_profile(current, kpi_name)
        if not current_profile.empty:
            ax.plot(current_profile["hour"], current_profile["value"], linewidth=1.4, label="Chu kỳ hiện tại")
        for reference in period.references:
            source = _mean_daily_cycle(_period_slice(pair_df, reference.start, reference.end))
            ref_profile = source[source["kpi_name"].astype(str) == str(kpi_name)].copy()
            if ref_profile.empty:
                continue
            ref_profile["hour"] = ref_profile["minute_of_day"] / 60.0
            short_label = reference.label.replace("Trung bình chu kỳ ngày trong ", "TB ")
            ax.plot(ref_profile["hour"], ref_profile["value"], linewidth=1.1, label=short_label)
        ax.set_xlim(0, 24)
        ax.set_xlabel("Giờ trong ngày")

    ax.set_title(f"{ne_id} / {cell_id} — {kpi_name}")
    ax.set_ylabel("Giá trị KPI")
    ax.grid(True, alpha=0.25)
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _build_charts(
    df: pd.DataFrame,
    period: HealthPeriod,
    detection: dict[str, Any],
) -> tuple[tuple[str, bytes], ...]:
    """Detailed 7-KPI chart for each of the top 5 NE-Cell pairs."""

    top_pairs = detection.get("top_pairs", pd.DataFrame())
    details = detection.get("top_pair_kpis", pd.DataFrame())
    if top_pairs.empty or details.empty:
        return tuple()

    charts: list[tuple[str, bytes]] = []
    for pair in top_pairs.itertuples(index=False):
        pair_rows = details[
            (details["ne_id"].astype(str) == str(pair.ne_id))
            & (details["cell_id"].astype(str) == str(pair.cell_id))
        ].copy()
        if pair_rows.empty:
            continue
        label = f"#{int(pair.rank)} {pair.ne_id} / {pair.cell_id}"
        charts.append(
            (
                label,
                _make_pair_detail_chart(
                    df,
                    period,
                    detection,
                    str(pair.ne_id),
                    str(pair.cell_id),
                    pair_rows,
                ),
            )
        )
    return tuple(charts)


def _shade_anomaly_spans(
    ax: Any,
    spans: list[tuple[pd.Timestamp, pd.Timestamp, str]],
) -> None:
    """Shade anomaly windows identically on both companion charts."""

    used_profiles: set[str] = set()
    for span_start, span_end, profile in spans:
        profile_key = str(profile).upper()
        label = (
            f"Vùng bất thường - {profile_key}"
            if profile_key not in used_profiles
            else None
        )
        ax.axvspan(
            span_start,
            span_end,
            color=_ANOMALY_COLORS.get(profile_key, "#ef4444"),
            alpha=_ANOMALY_SHADE_ALPHA,
            label=label,
            linewidth=0,
        )
        used_profiles.add(profile_key)


def _make_anomaly_chart(
    df: pd.DataFrame,
    period: HealthPeriod,
    detection: dict[str, Any],
    ne_id: str,
    cell_id: str,
    kpi_name: str,
) -> bytes:
    pair = df[
        (df["ne_id"].astype(str) == str(ne_id))
        & (df["cell_id"].astype(str) == str(cell_id))
        & (df["kpi_name"].astype(str) == str(kpi_name))
    ].copy()
    current = _period_slice(pair, period.start, period.end)

    fig, ax = plt.subplots(figsize=(8.2, 3.1))
    if not current.empty:
        ax.plot(current["timestamp"], current["value"], linewidth=1.2, color="#1f77b4", label="KPI trong kỳ")

    spans = _anomaly_spans_for_pair_kpi(detection, period, ne_id, cell_id, kpi_name)
    _shade_anomaly_spans(ax, spans)

    ax.set_title(f"{ne_id} / {cell_id} — {kpi_name}", fontsize=10, fontweight="bold")
    ax.set_xlabel("Thời gian")
    ax.set_ylabel("Giá trị KPI")
    ax.grid(True, alpha=0.25)
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(fontsize=7, frameon=False)
    fig.autofmt_xdate(rotation=25)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _reference_period_by_label(period: HealthPeriod, label: str) -> ReferencePeriod | None:
    raw = str(label).strip()
    # Artifact comparison lưu reference_label dạng machine-readable, trong khi
    # HealthPeriod dùng nhãn người đọc. Map hai representation về cùng kỳ.
    machine_map = {
        "24H_TO_72H_AVG": 72,
        "24H_TO_144H_AVG": 144,
        "24H_TO_288H_AVG": 288,
    }
    if raw in machine_map:
        target_hours = machine_map[raw]
        for reference in period.references:
            if reference.aggregation != "mean_daily_cycle":
                continue
            hours_from_anchor = int(round((period.end - reference.start).total_seconds() / 3600.0))
            if hours_from_anchor == target_hours:
                return reference
    if raw == "PREVIOUS_WEEK":
        for reference in period.references:
            if reference.aggregation == "direct_window":
                return reference
    for reference in period.references:
        if str(reference.label) == raw:
            return reference
    return None


def _current_window_series(
    df: pd.DataFrame,
    period: HealthPeriod,
    ne_id: str,
    cell_id: str,
    kpi_name: str,
) -> pd.DataFrame:
    pair = df[
        (df["ne_id"].astype(str) == str(ne_id))
        & (df["cell_id"].astype(str) == str(cell_id))
        & (df["kpi_name"].astype(str) == str(kpi_name))
    ].copy()
    current = _period_slice(pair, period.start, period.end).copy()
    if current.empty:
        return pd.DataFrame(columns=["timestamp", "value"])
    return current[["timestamp", "value"]].sort_values("timestamp").reset_index(drop=True)


def _reference_overlay_series(
    df: pd.DataFrame,
    period: HealthPeriod,
    reference: ReferencePeriod,
    ne_id: str,
    cell_id: str,
    kpi_name: str,
) -> pd.DataFrame:
    pair = df[
        (df["ne_id"].astype(str) == str(ne_id))
        & (df["cell_id"].astype(str) == str(cell_id))
        & (df["kpi_name"].astype(str) == str(kpi_name))
    ].copy()
    frame = _period_slice(pair, reference.start, reference.end).copy()
    if frame.empty:
        return pd.DataFrame(columns=["timestamp", "value"])

    duration_hours = max(int((period.end - period.start).total_seconds() / 3600), 1)
    if reference.aggregation == "mean_daily_cycle":
        frame["offset"] = (((frame["timestamp"] - reference.start).dt.total_seconds() / 3600.0) % 24.0).round(6)
        grouped = frame.groupby("offset", sort=True)["value"].mean().reset_index()
        grouped["timestamp"] = period.start + pd.to_timedelta(grouped["offset"], unit="h")
        return grouped[["timestamp", "value"]].sort_values("timestamp").reset_index(drop=True)

    frame["offset"] = (((frame["timestamp"] - reference.start).dt.total_seconds() / 3600.0) % duration_hours).round(6)
    grouped = frame.groupby("offset", sort=True)["value"].mean().reset_index()
    grouped["timestamp"] = period.start + pd.to_timedelta(grouped["offset"], unit="h")
    return grouped[["timestamp", "value"]].sort_values("timestamp").reset_index(drop=True)


def _make_reference_comparison_chart(
    df: pd.DataFrame,
    period: HealthPeriod,
    row: pd.Series,
) -> bytes:
    ne_id = str(row.get("ne_id", ""))
    cell_id = str(row.get("cell_id", ""))
    kpi_name = str(row.get("kpi_name", ""))
    label = str(row.get("comparison_basis", "baseline tham chiếu"))
    reference = _reference_period_by_label(period, str(row.get("reference_label", "")))
    current = _current_window_series(df, period, ne_id, cell_id, kpi_name)
    reference_series = (
        _reference_overlay_series(df, period, reference, ne_id, cell_id, kpi_name)
        if reference is not None
        else pd.DataFrame(columns=["timestamp", "value"])
    )

    fig, ax = plt.subplots(figsize=(8.2, 3.1))
    if not current.empty:
        ax.plot(current["timestamp"], current["value"], linewidth=1.15, color="#1f77b4", label="Chu kỳ hiện tại")
    if not reference_series.empty:
        ax.plot(reference_series["timestamp"], reference_series["value"], linewidth=1.15, color="#dc2626", linestyle="--", label=label)

    spans = _anomaly_spans_for_pair_kpi({"aligned_frame": pd.DataFrame([row])}, period, ne_id, cell_id, kpi_name)
    _shade_anomaly_spans(ax, spans)

    ax.set_title(f"{ne_id} / {cell_id} — so với {label}", fontsize=10, fontweight="bold")
    ax.set_xlabel("Thời gian")
    ax.set_ylabel("Giá trị KPI")
    ax.grid(True, alpha=0.25)
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(fontsize=7, frameon=False)
    fig.autofmt_xdate(rotation=25)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _build_anomaly_chart_pairs(
    df: pd.DataFrame,
    period: HealthPeriod,
    anomalies: pd.DataFrame,
) -> tuple[dict[str, Any], ...]:
    if anomalies.empty:
        return tuple()
    pairs: list[dict[str, Any]] = []
    for idx, row in anomalies.reset_index(drop=True).iterrows():
        pairs.append(
            {
                "key": (str(row["ne_id"]), str(row["cell_id"]), str(row["kpi_name"]), str(row["comparison_basis"])),
                "label": f"#{idx + 1} {row['ne_id']} / {row['cell_id']} — {row['kpi_name']}",
                # Một biểu đồ là đủ: biểu đồ so sánh này đã chứa cả chu kỳ hiện tại
                # và baseline tham chiếu, đồng thời giữ vùng tô bất thường.
                "reference_chart": _make_reference_comparison_chart(df, period, row),
            }
        )
    return tuple(pairs)


def _build_anomaly_charts(
    df: pd.DataFrame,
    period: HealthPeriod,
    detection: dict[str, Any],
) -> tuple[tuple[str, bytes], ...]:
    aligned = detection.get("aligned_frame", pd.DataFrame())
    if aligned is None or aligned.empty:
        return tuple()
    anomaly = aligned.get("anomaly_flag", pd.Series(False, index=aligned.index)).fillna(False).astype(bool)
    work = aligned.loc[anomaly, ["ne_id", "cell_id", "kpi_name"]].drop_duplicates()
    if work.empty:
        return tuple()

    charts: list[tuple[str, bytes]] = []
    for row in work.sort_values(["ne_id", "cell_id", "kpi_name"]).itertuples(index=False):
        label = f"{row.ne_id} / {row.cell_id} — {row.kpi_name}"
        charts.append(
            (
                label,
                _make_anomaly_chart(
                    df,
                    period,
                    detection,
                    str(row.ne_id),
                    str(row.cell_id),
                    str(row.kpi_name),
                ),
            )
        )
    return tuple(charts)


def _executive_and_conclusion(
    period: HealthPeriod,
    summary: pd.DataFrame,
    detection: dict[str, Any],
    trend: dict[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    executive: list[str] = []
    conclusion: list[str] = []

    if detection.get("aligned"):
        anomaly_count = int(detection.get("anomalies", 0))
        anomalous_pairs = int(detection.get("anomalous_pair_count", 0))
        anomalous_pair_kpis = int(detection.get("anomalous_pair_kpi_count", 0))
        executive.append(
            f"Trong 7 KPI chính có {anomalous_pair_kpis} tổ hợp NE-Cell/KPI bất thường "
            f"trên {anomalous_pairs} cặp NE-Cell; có {anomaly_count} phép so sánh bị gắn cờ."
        )
        conclusion.append(
            "Có bất thường cần rà soát trong kỳ."
            if anomaly_count
            else "Không phát hiện bất thường trên 7 KPI chính trong kỳ."
        )
    elif detection.get("available"):
        executive.append("Artifact phát hiện bất thường hiện có không cùng mốc thời gian với kỳ báo cáo này.")
    else:
        executive.append("Chưa có artifact phát hiện bất thường đồng bộ với kỳ báo cáo.")

    trend_frame = trend.get("trend", pd.DataFrame())
    if not trend_frame.empty and "trend_label" in trend_frame.columns:
        degrading = trend_frame[
            trend_frame["kpi_name"].astype(str).isin(FOCUS7_KPIS)
            & (trend_frame["trend_label"].astype(str).str.lower() == "degrading")
        ]
        degrading_ne_count = int(degrading["ne_id"].nunique()) if "ne_id" in degrading.columns else 0
        executive.append(f"Có {degrading_ne_count} NE có ít nhất một chuỗi KPI được phân loại xu hướng suy giảm.")

    return tuple(executive), tuple(conclusion)


def build_report_model(
    input_df: pd.DataFrame,
    *,
    period_kind: str,
    artifacts: HealthReportArtifacts = HealthReportArtifacts(),
) -> ReportModel:
    df = prepare_health_input(input_df)
    period = select_health_period(df, period_kind)
    current, summary = _period_summary(df, period)
    detection = _aligned_detection_snapshot(artifacts, period)
    trend = _trend_snapshot(artifacts, period)
    kpis = sorted(current["kpi_name"].astype(str).unique()) if not current.empty else []
    approved_kb, pending_zero = _knowledge_snapshot(artifacts, kpis)
    hierarchy_summary = _hierarchy_kpi_summary(current)
    degrading_ne = _degrading_ne_summary(trend.get("trend", pd.DataFrame()))
    anomaly_details = _full_anomaly_details(detection, period)
    period_chart = None
    charts = tuple()
    anomaly_chart_pairs = _build_anomaly_chart_pairs(df, period, anomaly_details)
    executive, conclusion = _executive_and_conclusion(period, summary, detection, trend)

    metadata = {
        "period_kind": period.kind,
        "period_start": period.start.isoformat(),
        "period_end": period.end.isoformat(),
        "rows": int(len(current)),
        "ne_count": int(current["ne_id"].nunique()) if not current.empty else 0,
        "cell_count": int(current["cell_id"].nunique()) if not current.empty else 0,
        "kpi_count": int(current["kpi_name"].nunique()) if not current.empty else 0,
        "focus_kpi_count": len(FOCUS7_KPIS),
        "anomalous_pair_count": int(detection.get("anomalous_pair_count", 0)),
        "anomalous_pair_kpi_count": int(detection.get("anomalous_pair_kpi_count", 0)),
        "anomaly_instances": int(detection.get("anomalies", 0)),
        "distinctive_score": period.distinctive_score,
        "approved_kb_matches": len(approved_kb),
        "pending_zero_variance_notes": len(pending_zero),
        "reference_periods": [
            {"label": ref.label, "start": ref.start.isoformat(), "end": ref.end.isoformat()}
            for ref in period.references
        ],
    }
    return ReportModel(
        period=period,
        current=current,
        kpi_summary=summary,
        hierarchy_summary=hierarchy_summary,
        degrading_ne=degrading_ne,
        anomaly_details=anomaly_details,
        metadata=metadata,
        detection=detection,
        trend=trend,
        approved_kb=approved_kb,
        pending_zero_variance=pending_zero,
        period_chart=period_chart,
        charts=charts,
        anomaly_chart_pairs=anomaly_chart_pairs,
        executive_summary=executive,
        overall_conclusion=conclusion,
    )


def generate_health_report_html(
    input_df: pd.DataFrame,
    *,
    period_kind: str,
    output_path: str | Path,
    artifacts: HealthReportArtifacts = HealthReportArtifacts(),
    title: str = "RKAA - Báo cáo sức khỏe mạng",
) -> tuple[Path, HealthPeriod, dict[str, Any]]:
    model = build_report_model(input_df, period_kind=period_kind, artifacts=artifacts)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_render_html(title=title, model=model), encoding="utf-8")
    return output, model.period, model.metadata


def generate_health_report_pdf(
    input_df: pd.DataFrame,
    *,
    period_kind: str,
    output_path: str | Path,
    artifacts: HealthReportArtifacts = HealthReportArtifacts(),
    title: str = "RKAA - Báo cáo sức khỏe mạng",
) -> tuple[Path, HealthPeriod, dict[str, Any]]:
    model = build_report_model(input_df, period_kind=period_kind, artifacts=artifacts)
    output = Path(output_path)
    if output.suffix.lower() != ".pdf":
        output = output.with_suffix(".pdf")
    output.parent.mkdir(parents=True, exist_ok=True)
    _render_pdf(output, title=title, model=model)
    return output, model.period, model.metadata


def _fmt(value: Any, digits: int = 3) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if not np.isfinite(number):
        return "-"
    return f"{number:,.{digits}f}"


def _reference_html(period: HealthPeriod) -> str:
    rows = "".join(
        f"<tr><td>{escape(ref.label)}</td><td>{escape(ref.start.isoformat())}</td>"
        f"<td>{escape(ref.end.isoformat())}</td></tr>"
        for ref in period.references
    )
    return rows or '<tr><td colspan="3">Không có kỳ tham chiếu.</td></tr>'



def _top_pairs_html(detection: dict[str, Any], pair_chart_map: dict[str, bytes] | None = None) -> tuple[str, str]:
    ranking = detection.get("top_pairs", pd.DataFrame())
    details = detection.get("top_pair_kpis", pd.DataFrame())
    if ranking.empty:
        message = (
            "<p>Không có cặp NE-Cell nào có KPI bị gắn cờ bất thường trong kỳ, "
            "hoặc artifact phát hiện không đồng bộ với kỳ báo cáo.</p>"
        )
        return message, message

    ranking_rows = "".join(
        f"<tr><td>{int(row.rank)}</td><td>{escape(str(row.ne_id))}</td>"
        f"<td>{escape(str(row.cell_id))}</td>"
        f"<td><b>{int(row.anomalous_kpi_count)}/7</b></td>"
        f"<td>{int(row.anomaly_instances)}</td>"
        f"<td>{_fmt(row.max_abs_delta_percent, 2)}%</td></tr>"
        for row in ranking.itertuples(index=False)
    )
    ranking_html = (
        "<p>Xếp hạng theo số KPI bất thường khác nhau trong đúng 7 KPI chính; "
        "số instance chỉ dùng làm tiêu chí phụ để tránh một KPI có nhiều profile làm phồng thứ hạng.</p>"
        "<table><thead><tr><th>#</th><th>NE</th><th>Cell</th>"
        "<th>KPI bất thường</th><th>Instance bất thường</th><th>|Delta %| lớn nhất</th>"
        f"</tr></thead><tbody>{ranking_rows}</tbody></table>"
    )

    pair_chart_map = pair_chart_map or {}
    detail_blocks: list[str] = []
    for pair in ranking.itertuples(index=False):
        pair_details = details[
            (details["ne_id"].astype(str) == str(pair.ne_id))
            & (details["cell_id"].astype(str) == str(pair.cell_id))
        ]
        rows = []
        for kpi in FOCUS7_KPIS:
            matched = pair_details[pair_details["kpi_name"].astype(str) == kpi]
            if matched.empty:
                rows.append(
                    f"<tr><td>{escape(kpi)}</td><td>Không có dữ liệu</td>"
                    "<td>0</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>"
                )
                continue
            item = matched.iloc[0]
            is_anomaly = bool(item["anomaly_flag"])
            status = "BẤT THƯỜNG" if is_anomaly else "Bình thường"
            status_class = "bad" if is_anomaly else "ok"
            delta = _fmt(item["delta_percent"], 2)
            delta_text = f"{delta}%" if delta != "-" else "-"
            rows.append(
                f"<tr><td>{escape(kpi)}</td><td class='{status_class}'><b>{status}</b></td>"
                f"<td>{int(item['anomaly_instances'])}</td>"
                f"<td>{_fmt(item['current_mean'])}</td>"
                f"<td>{_fmt(item['reference_mean'])}</td>"
                f"<td>{delta_text}</td>"
                f"<td>{escape(str(item['comparison_context']))}</td></tr>"
            )
        pair_label = f"#{int(pair.rank)} {pair.ne_id} / {pair.cell_id}"
        chart_html = ""
        if pair_label in pair_chart_map:
            chart_html = (
                f'<figure><img alt="{escape(pair_label)}" src="data:image/png;base64,{base64.b64encode(pair_chart_map[pair_label]).decode("ascii")}">' 
                f'<figcaption>{escape(pair_label)} — đủ 7 KPI trong kỳ; vùng tô màu là khoảng thời gian đang bị gắn cờ bất thường.</figcaption></figure>'
            )
        detail_blocks.append(
            f"<div class='pair-card'><h3>{escape(pair_label)} — {int(pair.anomalous_kpi_count)}/7 KPI bất thường</h3>"
            + chart_html +
            "<table><thead><tr><th>KPI</th><th>Trạng thái</th><th>Instance</th>"
            "<th>Mean hiện tại</th><th>Mean tham chiếu</th><th>Delta %</th><th>Ngữ cảnh xấu nhất</th>"
            f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
        )
    return ranking_html, "".join(detail_blocks)

def _render_html(*, title: str, model: ReportModel) -> str:
    period = model.period
    metadata = model.metadata
    executive_html = "".join(f"<li>{escape(item)}</li>" for item in model.executive_summary)

    hierarchy = model.hierarchy_summary
    if hierarchy.empty:
        hierarchy_html = "<p>Không có dữ liệu KPI để tổng hợp theo NE.</p>"
    else:
        rows: list[str] = []
        for ne_id, group in hierarchy.groupby("entity", dropna=False, sort=True):
            group = group.sort_values("kpi_name", kind="stable")
            first = True
            rowspan = len(group)
            for row in group.itertuples(index=False):
                ne_cell = (
                    f'<td rowspan="{rowspan}" class="ne-id"><b>{escape(str(ne_id))}</b></td>'
                    if first
                    else ""
                )
                first = False
                rows.append(
                    "<tr>"
                    + ne_cell
                    + f"<td>{escape(str(row.kpi_name))}</td>"
                    + f"<td>{int(row.count)}</td><td>{_fmt(row.mean)}</td>"
                    + f"<td>{_fmt(row.p05)}</td><td>{_fmt(row.p95)}</td></tr>"
                )
        hierarchy_html = (
            "<table><thead><tr><th>NE</th><th>KPI</th><th>Số mẫu</th>"
            "<th>Mean</th><th>P05</th><th>P95</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )

    degrading = model.degrading_ne
    if degrading.empty:
        degrading_html = "<p>Không có NE nào được xác định xu hướng suy giảm, hoặc chưa cung cấp artifact xu hướng.</p>"
    else:
        rows = "".join(
            f"<tr><td>{escape(str(row.ne_id))}</td><td>{int(row.degrading_kpi_count)}</td>"
            f"<td>{int(row.affected_cell_count)}</td><td>{int(row.degrading_series_count)}</td>"
            f"<td>{escape(str(row.kpis))}</td></tr>"
            for row in degrading.itertuples(index=False)
        )
        degrading_html = (
            "<table><thead><tr><th>NE</th><th>KPI suy giảm</th><th>Cell ảnh hưởng</th>"
            f"<th>Số chuỗi suy giảm</th><th>Danh sách KPI</th></tr></thead><tbody>{rows}</tbody></table>"
        )

    anomalies = model.anomaly_details
    if anomalies.empty:
        if model.detection.get("aligned"):
            anomaly_html = "<p>Không phát hiện bất thường trên 7 KPI chính trong kỳ này.</p>"
        elif model.detection.get("available"):
            anomaly_html = "<p>Artifact bất thường hiện có không đồng bộ với mốc thời gian của kỳ báo cáo.</p>"
        else:
            anomaly_html = "<p>Chưa cung cấp artifact phát hiện bất thường cho kỳ báo cáo.</p>"
    else:
        anomaly_rows: list[str] = []
        for row in anomalies.itertuples(index=False):
            delta = _fmt(row.delta_percent, 2)
            anomaly_rows.append(
                "<tr class='anomaly-row'>"
                f"<td>{escape(str(row.ne_id))}</td><td>{escape(str(row.cell_id))}</td>"
                f"<td><b>{escape(str(row.kpi_name))}</b></td>"
                f"<td>{escape(str(row.comparison_basis))}</td>"
                f"<td>{_fmt(row.current_mean)}</td><td>{_fmt(row.reference_mean)}</td>"
                f"<td>{delta + '%' if delta != '-' else '-'}</td>"
                f"<td>{escape(str(row.detection_reason))}</td></tr>"
            )

        chart_pair_map = {tuple(item["key"]): item for item in model.anomaly_chart_pairs}
        item_blocks: list[str] = []
        for index, row in enumerate(anomalies.itertuples(index=False), start=1):
            delta = _fmt(row.delta_percent, 2)
            chart_key = (str(row.ne_id), str(row.cell_id), str(row.kpi_name), str(row.comparison_basis))
            chart_pair = chart_pair_map.get(chart_key, {})
            reference_html = ""
            if chart_pair.get("reference_chart") is not None:
                reference_html = (
                    f'<figure class="anomaly-chart"><img alt="comparison-{index}" '
                    f'src="data:image/png;base64,{base64.b64encode(chart_pair["reference_chart"]).decode("ascii")}">'
                    f'<figcaption>Biểu đồ so sánh — chu kỳ hiện tại và baseline tham chiếu: {escape(str(row.comparison_basis))}; vùng tô màu là khoảng thời gian bị gắn cờ bất thường.</figcaption></figure>'
                )
            item_blocks.append(
                "<div class='anomaly-item'>"
                f"<h3>#{index} {escape(str(row.ne_id))} / {escape(str(row.cell_id))} — {escape(str(row.kpi_name))}</h3>"
                "<table><tbody>"
                f"<tr><th>So với</th><td>{escape(str(row.comparison_basis))}</td></tr>"
                f"<tr><th>Mean kỳ hiện tại</th><td>{_fmt(row.current_mean)}</td></tr>"
                f"<tr><th>Mean tham chiếu</th><td>{_fmt(row.reference_mean)}</td></tr>"
                f"<tr><th>Delta %</th><td>{delta + '%' if delta != '-' else '-'}</td></tr>"
                f"<tr><th>Lý do gắn cờ</th><td>{escape(str(row.detection_reason))}</td></tr>"
                "</tbody></table>"
                f"<div class='anomaly-charts single-chart'>{reference_html}</div>"
                "</div>"
            )
        anomaly_html = (
            f"<p>Liệt kê đầy đủ <b>{len(anomalies)}</b> phép so sánh bị gắn cờ trong kỳ. "
            "Mỗi mục nêu KPI bất thường, baseline tham chiếu, lý do detector gắn cờ và một biểu đồ so sánh chu kỳ hiện tại với baseline.</p>"
            + "".join(item_blocks)
        )

    distinctive = (
        f'<div class="metric"><span>Điểm đặc trưng</span><b>{_fmt(period.distinctive_score, 3)}</b></div>'
        if period.distinctive_score is not None
        else ""
    )

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>
body{{font-family:Arial,sans-serif;margin:0;background:#f4f6f8;color:#1f2937}}main{{max-width:1380px;margin:auto;padding:20px}}
header{{background:#fff;padding:18px;border-radius:12px;margin-bottom:16px}}h1{{margin:0 0 6px}}h2{{margin-top:0}}h3{{margin-top:18px}}.muted{{color:#64748b}}
.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin:14px 0}}.metric,section{{background:#fff;border-radius:12px;padding:14px}}
.metric span{{display:block;color:#64748b;font-size:12px}}.metric b{{font-size:23px}}section{{margin:14px 0;overflow:auto}}table{{width:100%;border-collapse:collapse;font-size:12px}}th,td{{padding:7px;border-bottom:1px solid #e5e7eb;text-align:left;vertical-align:top}}th{{background:#f8fafc;position:sticky;top:0}}
.notice{{border-left:4px solid #f59e0b;background:#fffbeb;padding:10px 12px;border-radius:6px;margin:10px 0}}.anomaly-row{{background:#fff7f7}}.anomaly-row:hover{{background:#fee2e2}}.ne-id{{vertical-align:top;background:#f8fafc}}.anomaly-item{{border:1px solid #e5e7eb;border-radius:10px;padding:12px;margin:12px 0;background:#fcfcfd}}.anomaly-item h3{{margin-top:0}}.anomaly-item table{{margin-top:8px}}.anomaly-item th{{width:180px;position:static;background:#f8fafc}}.anomaly-charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(500px,1fr));gap:14px;margin-top:12px}}.anomaly-charts.single-chart{{grid-template-columns:minmax(0,900px);justify-content:start}}figure.anomaly-chart{{margin:0;border:1px solid #e5e7eb;border-radius:10px;padding:8px;background:#fff}}figure.anomaly-chart img{{width:100%;height:auto}}figure.anomaly-chart figcaption{{font-size:12px;color:#64748b;margin-top:5px}}
@media(max-width:600px){{main{{padding:10px}}th,td{{font-size:11px;padding:5px}}.anomaly-charts{{grid-template-columns:1fr}}}}
@media print{{body{{background:#fff}}header,section{{break-inside:auto}}th{{position:static}}}}
</style></head><body><main>
<header><h1>{escape(title)}</h1><div class="muted">{escape(period.label)} - {escape(period.start.isoformat())} -> {escape(period.end.isoformat())}</div><p>{escape(period.selection_note)}</p></header>
<div class="metrics"><div class="metric"><span>Bản ghi KPI</span><b>{metadata['rows']:,}</b></div><div class="metric"><span>NE</span><b>{metadata['ne_count']}</b></div><div class="metric"><span>Cell</span><b>{metadata['cell_count']}</b></div><div class="metric"><span>KPI</span><b>{metadata['kpi_count']}</b></div><div class="metric"><span>Bất thường</span><b>{len(anomalies)}</b></div>{distinctive}</div>
<section><h2>1. Tóm tắt điều hành</h2><ul>{executive_html}</ul></section>
<section><h2>2. Tổng hợp KPI theo NE</h2>{hierarchy_html}</section>
<section><h2>3. Danh sách NE có xu hướng suy giảm</h2>{degrading_html}</section>
<section><h2>4. Bất thường được phát hiện trong kỳ</h2>{anomaly_html}</section>
<footer class="muted">Báo cáo được sinh tự động bởi RKAA.</footer></main></body></html>"""


def _pdf_text_page(pdf: PdfPages, title: str, lines: list[str]) -> None:
    fig = plt.figure(figsize=(8.27, 11.69))
    ax = fig.add_axes([0.08, 0.06, 0.84, 0.88])
    ax.axis("off")
    ax.text(0, 1.0, title, fontsize=16, fontweight="bold", va="top")
    y = 0.94
    for line in lines:
        wrapped = textwrap.wrap(str(line), width=100) or [""]
        for part in wrapped:
            ax.text(0, y, part, fontsize=9.5, va="top")
            y -= 0.027
            if y < 0.04:
                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)
                fig = plt.figure(figsize=(8.27, 11.69))
                ax = fig.add_axes([0.08, 0.06, 0.84, 0.88])
                ax.axis("off")
                y = 0.96
        y -= 0.01
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def _pdf_table_pages(
    pdf: PdfPages,
    title: str,
    frame: pd.DataFrame,
    columns: list[str],
    *,
    rows_per_page: int = 22,
    font_size: float = 6.5,
    wrap_width: int = 24,
) -> None:
    if frame.empty:
        _pdf_text_page(pdf, title, ["Không có dữ liệu."])
        return

    for page_index, offset in enumerate(range(0, len(frame), rows_per_page), start=1):
        display = frame.iloc[offset : offset + rows_per_page][columns].copy()
        for column in display.columns:
            if pd.api.types.is_numeric_dtype(display[column]):
                display[column] = display[column].map(lambda value: _fmt(value, 2))
            else:
                display[column] = display[column].astype(str).map(
                    lambda value: "\n".join(textwrap.wrap(value, wrap_width))
                )
        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        ax.axis("off")
        page_title = title if len(frame) <= rows_per_page else f"{title} - trang {page_index}"
        ax.set_title(page_title, fontsize=13, fontweight="bold", pad=14)
        table = ax.table(
            cellText=display.values,
            colLabels=display.columns,
            loc="center",
            cellLoc="left",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(font_size)
        table.scale(1, 1.25)
        fig.tight_layout()
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)


def _pdf_anomaly_pages(pdf: PdfPages, anomalies: pd.DataFrame, chart_pairs: tuple[dict[str, Any], ...]) -> None:
    if anomalies.empty:
        _pdf_text_page(pdf, "Bất thường được phát hiện trong kỳ", ["Không có bất thường hoặc chưa có artifact đồng bộ."])
        return

    chart_pair_map = {tuple(item["key"]): item for item in chart_pairs}
    for global_index, (_, row) in enumerate(anomalies.iterrows(), start=1):
        fig = plt.figure(figsize=(8.27, 11.69))
        ax = fig.add_axes([0.06, 0.78, 0.88, 0.18])
        ax.axis("off")
        ax.text(0, 1.0, f"Bất thường #{global_index}", fontsize=15, fontweight="bold", va="top", transform=ax.transAxes)
        delta = _fmt(row.get("delta_percent"), 2)
        lines = [
            f"NE/Cell: {row['ne_id']} / {row['cell_id']}",
            f"KPI bất thường: {row['kpi_name']}",
            f"So với: {row['comparison_basis']}",
            f"Mean kỳ hiện tại: {_fmt(row.get('current_mean'))} | Mean tham chiếu: {_fmt(row.get('reference_mean'))} | Delta: {delta + '%' if delta != '-' else '-'}",
            f"Lý do gắn cờ: {row['detection_reason']}",
        ]
        y = 0.86
        for line in lines:
            for part in textwrap.wrap(str(line), width=105) or [""]:
                ax.text(0, y, part, fontsize=8.8, va="top", transform=ax.transAxes)
                y -= 0.11

        chart_key = (str(row['ne_id']), str(row['cell_id']), str(row['kpi_name']), str(row['comparison_basis']))
        pair = chart_pair_map.get(chart_key)
        if pair is not None and pair.get("reference_chart") is not None:
            ax_chart = fig.add_axes([0.08, 0.16, 0.84, 0.48])
            ax_chart.axis("off")
            image = plt.imread(io.BytesIO(pair["reference_chart"]), format="png")
            ax_chart.imshow(image)
            ax_chart.set_title("Chu kỳ hiện tại so với baseline tham chiếu", fontsize=10.5)

        pdf.savefig(fig)
        plt.close(fig)


def _render_pdf(path: Path, *, title: str, model: ReportModel) -> None:
    with PdfPages(path) as pdf:
        info_lines = [
            f"Kỳ phân tích: {model.period.label}",
            f"Thời gian: {model.period.start.isoformat()} -> {model.period.end.isoformat()}",
            model.period.selection_note,
            "",
            "Tóm tắt điều hành:",
            *[f"- {item}" for item in model.executive_summary],
        ]
        _pdf_text_page(pdf, title, info_lines)

        hierarchy = model.hierarchy_summary.copy()
        if hierarchy.empty:
            _pdf_text_page(pdf, "Tổng hợp KPI theo NE", ["Không có dữ liệu KPI để tổng hợp theo NE."])
        else:
            subset = hierarchy[hierarchy["level"].astype(str) == "NE"].copy()
            subset = subset.rename(
                columns={
                    "entity": "NE",
                    "kpi_name": "KPI",
                    "count": "Số mẫu",
                    "mean": "Mean",
                    "p05": "P05",
                    "p95": "P95",
                }
            )
            subset = subset.sort_values(["NE", "KPI"], kind="stable").reset_index(drop=True)
            subset.loc[subset["NE"].duplicated(), "NE"] = ""
            _pdf_table_pages(
                pdf,
                "Tổng hợp KPI theo NE",
                subset,
                ["NE", "KPI", "Số mẫu", "Mean", "P05", "P95"],
                rows_per_page=22,
                font_size=6.8,
                wrap_width=28,
            )

        degrading = model.degrading_ne.copy()
        if not degrading.empty:
            degrading = degrading.rename(
                columns={
                    "ne_id": "NE",
                    "degrading_kpi_count": "KPI suy giảm",
                    "affected_cell_count": "Cell ảnh hưởng",
                    "degrading_series_count": "Số chuỗi",
                    "kpis": "Danh sách KPI",
                }
            )
        _pdf_table_pages(
            pdf,
            "Danh sách NE có xu hướng suy giảm",
            degrading,
            ["NE", "KPI suy giảm", "Cell ảnh hưởng", "Số chuỗi", "Danh sách KPI"],
            rows_per_page=18,
            font_size=6.5,
            wrap_width=30,
        )

        _pdf_anomaly_pages(pdf, model.anomaly_details, model.anomaly_chart_pairs)


