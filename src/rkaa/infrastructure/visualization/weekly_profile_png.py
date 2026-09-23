"""PNG chart adapters for FR-402 weekly-cycle analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FIGURE_SIZE_INCHES = (6.0, 2.6)
CYCLE_FIGURE_SIZE_INCHES = (6.4, 5.6)

_REQUIRED_COLUMNS = {
    "ne_id",
    "cell_id",
    "kpi_name",
    "day_type",
    "minute_of_day",
    "mean",
}

_PROFILE_COLUMNS = {
    "ne_id",
    "cell_id",
    "kpi_name",
    "timestamp",
    "value",
    "day_type",
    "day_of_week",
}

_DAY_ORDER = [
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
    "SUNDAY",
]


@dataclass(frozen=True, slots=True)
class WeeklyWindow:
    label: str
    start: pd.Timestamp
    end: pd.Timestamp
    data: pd.DataFrame


def _png_path(output_path: str | Path) -> Path:
    path = Path(output_path)
    return path if path.suffix.lower() == ".png" else path.with_suffix(".png")


def _filter_metric(df: pd.DataFrame, *, ne_id: str, cell_id: str, kpi_name: str) -> pd.DataFrame:
    return df[
        (df["ne_id"].astype(str) == str(ne_id))
        & (df["cell_id"].astype(str) == str(cell_id))
        & (df["kpi_name"].astype(str) == str(kpi_name))
    ].copy()


def _prepare_profiled_frame(
    profiled_df: pd.DataFrame,
    *,
    ne_id: str,
    cell_id: str,
    kpi_name: str,
) -> pd.DataFrame:
    missing = sorted(_PROFILE_COLUMNS.difference(profiled_df.columns))
    if missing:
        raise ValueError(f"Thiếu cột để vẽ biểu đồ FR-402: {', '.join(missing)}")

    selected = _filter_metric(profiled_df, ne_id=ne_id, cell_id=cell_id, kpi_name=kpi_name)
    if selected.empty:
        raise ValueError("Không có dữ liệu FR-402 cho NE/Cell/KPI đã chọn")

    selected["timestamp"] = pd.to_datetime(selected["timestamp"], errors="coerce", utc=True, format="mixed")
    selected["value"] = pd.to_numeric(selected["value"], errors="coerce")
    selected = selected.dropna(subset=["timestamp", "value"]).copy()
    if selected.empty:
        raise ValueError("Dữ liệu FR-402 không có timestamp/value numeric để vẽ")

    if "minute_of_day" not in selected.columns:
        local = selected["timestamp"]
        selected["minute_of_day"] = local.dt.hour * 60 + local.dt.minute
    selected["minute_of_day"] = pd.to_numeric(selected["minute_of_day"], errors="coerce")
    selected = selected.dropna(subset=["minute_of_day"]).copy()
    selected["minute_of_day"] = selected["minute_of_day"].astype(int)
    return selected.sort_values("timestamp")


def _window(df: pd.DataFrame, *, end: pd.Timestamp, duration: pd.Timedelta) -> pd.DataFrame:
    start = end - duration
    return df[(df["timestamp"] > start) & (df["timestamp"] <= end)].copy()


def build_weekly_windows(
    profiled_df: pd.DataFrame,
    *,
    ne_id: str,
    cell_id: str,
    kpi_name: str,
    anchor_end: pd.Timestamp | str | None = None,
    current_window_days: int = 7,
) -> tuple[WeeklyWindow, WeeklyWindow]:
    selected = _prepare_profiled_frame(
        profiled_df,
        ne_id=ne_id,
        cell_id=cell_id,
        kpi_name=kpi_name,
    )
    if anchor_end is None:
        resolved_anchor = selected["timestamp"].max()
    else:
        resolved_anchor = pd.to_datetime(anchor_end, errors="coerce", utc=True)
        if pd.isna(resolved_anchor):
            raise ValueError("anchor_end không phải timestamp hợp lệ")

    duration = pd.Timedelta(days=current_window_days)
    current = _window(selected, end=resolved_anchor, duration=duration)
    previous_end = resolved_anchor - duration
    previous = _window(selected, end=previous_end, duration=duration)

    current = current.copy()
    previous = previous.copy()
    current_start = resolved_anchor - duration
    previous_start = previous_end - duration
    current["week_hour"] = (current["timestamp"] - current_start).dt.total_seconds() / 3600.0
    previous["week_hour"] = (previous["timestamp"] - previous_start).dt.total_seconds() / 3600.0

    return (
        WeeklyWindow("CURRENT_WEEK", current_start, resolved_anchor, current),
        WeeklyWindow("PREVIOUS_WEEK", previous_start, previous_end, previous),
    )


def _day_type_detail(window_df: pd.DataFrame) -> pd.DataFrame:
    if window_df.empty:
        return window_df.copy()
    detail = (
        window_df.groupby(["day_type", "minute_of_day"], dropna=False, sort=True)
        .agg(value=("value", "mean"))
        .reset_index()
    )
    return detail.sort_values(["day_type", "minute_of_day"])


def write_weekly_cycle_png(
    profiled_df: pd.DataFrame,
    *,
    ne_id: str,
    cell_id: str,
    kpi_name: str,
    output_path: str | Path,
    anchor_end: pd.Timestamp | str | None = None,
    current_window_days: int = 7,
    dpi: int = 160,
) -> Path:
    """Render FR-402 as four line charts.

    1. Tuần hiện tại.
    2. Tuần trước.
    3. Current week WEEKDAY/WEEKEND detail.
    4. Previous week WEEKDAY/WEEKEND detail.
    """

    current, previous = build_weekly_windows(
        profiled_df,
        ne_id=ne_id,
        cell_id=cell_id,
        kpi_name=kpi_name,
        anchor_end=anchor_end,
        current_window_days=current_window_days,
    )

    path = _png_path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    frames = [current.data, previous.data]
    non_empty_values = [frame["value"] for frame in frames if not frame.empty]
    if not non_empty_values:
        raise ValueError("Không đủ dữ liệu tuần hiện tại/tuần trước để vẽ FR-402")
    all_values = pd.concat(non_empty_values, ignore_index=True)
    y_min = float(all_values.min())
    y_max = float(all_values.max())
    margin = max((y_max - y_min) * 0.08, 0.5) if y_min != y_max else max(abs(y_min) * 0.01, 1.0)

    fig, axes = plt.subplots(2, 2, figsize=CYCLE_FIGURE_SIZE_INCHES, sharey=True)
    ax1, ax2, ax3, ax4 = axes.ravel()

    for ax, window, title in (
        (ax1, current, "Hồ sơ tuần hiện tại"),
        (ax2, previous, "Hồ sơ tuần trước"),
    ):
        if window.data.empty:
            ax.text(0.5, 0.5, "Không đủ dữ liệu", transform=ax.transAxes, ha="center", va="center")
        else:
            ax.plot(window.data["week_hour"], window.data["value"], linewidth=1.2, color="#1f4e79")
        subtitle = f"({window.start.strftime('%Y-%m-%d %H:%M')} → {window.end.strftime('%Y-%m-%d %H:%M')}]"
        ax.set_title(f"{title}\n{subtitle}", fontsize=8)
        ax.set_xlim(0, current_window_days * 24)
        ax.set_xticks(range(0, current_window_days * 24 + 1, 24))
        ax.grid(True, alpha=0.25)
        ax.set_ylabel("KPI")
        ax.set_xlabel("Giờ trong tuần")

    for ax, detail_source, title in (
        (ax3, current.data, "Chi tiết ngày thường/cuối tuần hiện tại"),
        (ax4, previous.data, "Chi tiết ngày thường/cuối tuần tuần trước"),
    ):
        detail = _day_type_detail(detail_source)
        for day_type, linestyle in (("WEEKDAY", "-"), ("WEEKEND", "--")):
            subset = detail[detail["day_type"] == day_type]
            if subset.empty:
                continue
            ax.plot(
                subset["minute_of_day"] / 60.0,
                subset["value"],
                linewidth=1.4,
                linestyle=linestyle,
                label=("Ngày thường" if day_type == "WEEKDAY" else "Cuối tuần"),
            )
        ax.set_title(title, fontsize=8)
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 6))
        ax.grid(True, alpha=0.25)
        ax.set_xlabel("Giờ trong ngày")
        ax.set_ylabel("KPI")
        ax.legend(frameon=False, fontsize=7)

    fig.suptitle(f"FR-402 — {ne_id} / {cell_id} / {kpi_name}", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return path


def write_weekly_profile_png(
    overlay_df: pd.DataFrame,
    *,
    ne_id: str,
    cell_id: str,
    kpi_name: str,
    output_path: str | Path,
    dpi: int = 160,
) -> Path:
    """Plot mean KPI by time-of-day, comparing WEEKDAY and WEEKEND."""

    missing = sorted(_REQUIRED_COLUMNS.difference(overlay_df.columns))
    if missing:
        raise ValueError(f"Thiếu cột để vẽ biểu đồ FR-402: {', '.join(missing)}")

    selected = _filter_metric(overlay_df, ne_id=ne_id, cell_id=cell_id, kpi_name=kpi_name)
    if selected.empty:
        raise ValueError("Không có dữ liệu overlay FR-402 cho NE/Cell/KPI đã chọn")

    selected["mean"] = pd.to_numeric(selected["mean"], errors="coerce")
    selected["minute_of_day"] = pd.to_numeric(selected["minute_of_day"], errors="coerce")
    selected = selected.dropna(subset=["mean", "minute_of_day"])
    if selected.empty:
        raise ValueError("Overlay FR-402 không có giá trị số để vẽ")

    path = _png_path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=FIGURE_SIZE_INCHES)
    for day_type, linestyle in (("WEEKDAY", "-"), ("WEEKEND", "--")):
        subset = selected[selected["day_type"] == day_type].sort_values("minute_of_day")
        if subset.empty:
            continue
        ax.plot(
            subset["minute_of_day"] / 60.0,
            subset["mean"],
            linewidth=1.6,
            linestyle=linestyle,
            label=("Ngày thường" if day_type == "WEEKDAY" else "Cuối tuần"),
        )

    ax.set_title(f"{ne_id} / {cell_id} / {kpi_name} - Ngày thường và cuối tuần")
    ax.set_xlabel("Giờ trong ngày")
    ax.set_ylabel("Mean KPI")
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return path
