"""PNG chart adapters for FR-401 temporal analysis.

Two renderers are kept deliberately:

* ``write_temporal_profile_png`` is the legacy aggregated day/night profile
  renderer kept for backward compatibility.
* ``write_temporal_cycle_png`` is the FR-401 cycle renderer used by the main
  runner. It now plots four independent panels: the latest clean 24-hour cycle
  plus three *mean daily cycles* built from cumulative history windows
  ``(T-72h, T-24h]``, ``(T-144h, T-24h]``, and ``(T-288h, T-24h]`` (or the
  configured endpoints).

The Agg backend keeps rendering headless-safe on servers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Legacy single-panel canvas retained for compatibility with the old profile plot.
FIGURE_SIZE_INCHES = (6.0, 2.6)
# Four panels in a compact 2x2 layout.
CYCLE_FIGURE_SIZE_INCHES = (6.4, 5.6)

_PROFILE_REQUIRED_COLUMNS = {
    "ne_id",
    "cell_id",
    "kpi_name",
    "temporal_profile",
    "minute_of_day",
    "mean",
}

_CYCLE_REQUIRED_COLUMNS = {
    "ne_id",
    "cell_id",
    "kpi_name",
    "timestamp",
    "value",
    "temporal_profile",
}

_PROFILE_SHADE_COLORS = {
    "BUSY": "#ffd6d6",
    "TRANSITION": "#ffe6bf",
    "OFF_PEAK": "#d9ecff",
}


@dataclass(frozen=True, slots=True)
class DailyCycleWindow:
    """One FR-401 chart panel."""

    label: str
    title: str
    start: pd.Timestamp
    end: pd.Timestamp
    data: pd.DataFrame


def _png_path(output_path: str | Path) -> Path:
    path = Path(output_path)
    return path if path.suffix.lower() == ".png" else path.with_suffix(".png")


def _filter_metric(
    df: pd.DataFrame,
    *,
    ne_id: str,
    cell_id: str,
    kpi_name: str,
) -> pd.DataFrame:
    return df[
        (df["ne_id"].astype(str) == str(ne_id))
        & (df["cell_id"].astype(str) == str(cell_id))
        & (df["kpi_name"].astype(str) == str(kpi_name))
    ].copy()


def _prepare_cycle_frame(
    profiled_df: pd.DataFrame,
    *,
    ne_id: str,
    cell_id: str,
    kpi_name: str,
) -> pd.DataFrame:
    missing = sorted(_CYCLE_REQUIRED_COLUMNS.difference(profiled_df.columns))
    if missing:
        raise ValueError(f"Thiếu cột để vẽ chu kỳ FR-401: {', '.join(missing)}")

    selected = _filter_metric(
        profiled_df,
        ne_id=ne_id,
        cell_id=cell_id,
        kpi_name=kpi_name,
    )
    if selected.empty:
        raise ValueError("Không có dữ liệu FR-401 cho NE/Cell/KPI đã chọn")

    selected["timestamp"] = pd.to_datetime(
        selected["timestamp"], errors="coerce", utc=True, format="mixed"
    )
    selected["value"] = pd.to_numeric(selected["value"], errors="coerce")
    selected = selected.dropna(subset=["timestamp", "value"])
    if selected.empty:
        raise ValueError("Dữ liệu FR-401 không có timestamp/value numeric để vẽ")

    if "minute_of_day" not in selected.columns:
        local = selected["timestamp"]
        selected["minute_of_day"] = local.dt.hour * 60 + local.dt.minute
    selected["minute_of_day"] = pd.to_numeric(selected["minute_of_day"], errors="coerce")
    selected = selected.dropna(subset=["minute_of_day"]).copy()
    selected["minute_of_day"] = selected["minute_of_day"].astype(int)
    if "time_of_day" not in selected.columns:
        selected["time_of_day"] = (
            pd.to_timedelta(selected["minute_of_day"], unit="m").astype(str).str.slice(0, 5)
        )
    return selected.sort_values(["timestamp", "minute_of_day"])


def _range(frame: pd.DataFrame, *, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    return frame[(frame["timestamp"] > start) & (frame["timestamp"] <= end)].copy()


def _mean_daily_cycle(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    group_columns = ["minute_of_day", "time_of_day", "temporal_profile"]
    aggregated = (
        frame.groupby(group_columns, dropna=False, sort=True)
        .agg(value=("value", "mean"))
        .reset_index()
    )
    return aggregated.sort_values("minute_of_day")


def build_daily_cycle_windows(
    profiled_df: pd.DataFrame,
    *,
    ne_id: str,
    cell_id: str,
    kpi_name: str,
    anchor_end: pd.Timestamp | str | None = None,
    current_window_hours: int = 24,
    comparison_lags_hours: Sequence[int] = (72, 144, 288),
) -> list[DailyCycleWindow]:
    """Build the four FR-401 chart panels.

    Panel 1 is the concrete latest 24h clean cycle. Panels 2-4 are historical
    *mean daily cycles* from cumulative ranges ending at ``T-24h``.
    """

    if current_window_hours <= 0:
        raise ValueError("current_window_hours phải > 0")
    if any(int(lag) <= current_window_hours for lag in comparison_lags_hours):
        raise ValueError(
            "comparison_lags_hours phải lớn hơn current_window_hours để tạo range lịch sử"
        )

    selected = _prepare_cycle_frame(
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

    current_duration = pd.Timedelta(hours=current_window_hours)
    current_start = resolved_anchor - current_duration
    current = _range(selected, start=current_start, end=resolved_anchor)
    current = current.sort_values("minute_of_day")

    windows: list[DailyCycleWindow] = [
        DailyCycleWindow(
            label="CURRENT",
            title="Hiện tại (24h gần nhất)",
            start=current_start,
            end=resolved_anchor,
            data=current,
        )
    ]

    for lag_hours in comparison_lags_hours:
        history_start = resolved_anchor - pd.Timedelta(hours=int(lag_hours))
        history_end = current_start
        history = _range(selected, start=history_start, end=history_end)
        averaged = _mean_daily_cycle(history)
        windows.append(
            DailyCycleWindow(
                label=f"24H_TO_{int(lag_hours)}H_AVG",
                title=f"TB ngày: 24h → {int(lag_hours)}h trước",
                start=history_start,
                end=history_end,
                data=averaged,
            )
        )
    return windows


def _infer_profile_spans(frame: pd.DataFrame) -> list[tuple[str, float, float]]:
    if frame.empty or "temporal_profile" not in frame.columns or "minute_of_day" not in frame.columns:
        return []

    mapping = (
        frame[["minute_of_day", "temporal_profile"]]
        .dropna()
        .drop_duplicates()
        .sort_values("minute_of_day")
    )
    if mapping.empty:
        return []
    minutes = mapping["minute_of_day"].astype(int).unique().tolist()
    diffs = sorted({b - a for a, b in zip(minutes, minutes[1:]) if b > a})
    step_minutes = diffs[0] if diffs else 60

    spans: list[tuple[str, float, float]] = []
    for profile, subset in mapping.groupby("temporal_profile", sort=False):
        values = sorted(subset["minute_of_day"].astype(int).tolist())
        if not values:
            continue
        start = values[0]
        prev = values[0]
        for minute in values[1:]:
            if minute - prev > step_minutes:
                spans.append((str(profile), start / 60.0, (prev + step_minutes) / 60.0))
                start = minute
            prev = minute
        spans.append((str(profile), start / 60.0, (prev + step_minutes) / 60.0))
    return spans


def _shade_profile_regions(ax, spans: list[tuple[str, float, float]]) -> None:
    seen: set[str] = set()
    for profile, start_hour, end_hour in spans:
        color = _PROFILE_SHADE_COLORS.get(profile)
        if color is None:
            continue
        label = profile if profile not in seen else None
        ax.axvspan(start_hour, end_hour, color=color, alpha=0.35, label=label, zorder=0)
        seen.add(profile)


def write_temporal_cycle_png(
    profiled_df: pd.DataFrame,
    *,
    ne_id: str,
    cell_id: str,
    kpi_name: str,
    output_path: str | Path,
    anchor_end: pd.Timestamp | str | None = None,
    current_window_hours: int = 24,
    comparison_lags_hours: Sequence[int] = (72, 144, 288),
    dpi: int = 160,
) -> Path:
    """Render FR-401 as four independent 24-hour line charts."""

    windows = build_daily_cycle_windows(
        profiled_df,
        ne_id=ne_id,
        cell_id=cell_id,
        kpi_name=kpi_name,
        anchor_end=anchor_end,
        current_window_hours=current_window_hours,
        comparison_lags_hours=comparison_lags_hours,
    )
    if len(windows) != 4:
        raise ValueError("Ảnh FR-401 dạng 2x2 yêu cầu current + 3 reference cycles")

    spans = _infer_profile_spans(
        _prepare_cycle_frame(
            profiled_df,
            ne_id=ne_id,
            cell_id=cell_id,
            kpi_name=kpi_name,
        )
    )

    path = _png_path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(2, 2, figsize=CYCLE_FIGURE_SIZE_INCHES, sharex=True, sharey=True)
    axes_flat = axes.ravel()

    non_empty_values = [window.data["value"] for window in windows if not window.data.empty]
    if not non_empty_values:
        plt.close(fig)
        raise ValueError("Bốn cửa sổ FR-401 đều không có dữ liệu để vẽ")
    all_values = pd.concat(non_empty_values, ignore_index=True)
    y_min = float(all_values.min())
    y_max = float(all_values.max())
    margin = max((y_max - y_min) * 0.08, 0.5) if y_min != y_max else max(abs(y_min) * 0.01, 1.0)

    legend_handles = legend_labels = None
    for ax, window in zip(axes_flat, windows, strict=True):
        _shade_profile_regions(ax, spans)
        if window.data.empty:
            ax.text(0.5, 0.5, "Không đủ dữ liệu", transform=ax.transAxes, ha="center", va="center")
        else:
            ax.plot(
                window.data["minute_of_day"] / 60.0,
                window.data["value"],
                linewidth=1.5,
                color="#1f4e79",
                zorder=2,
            )
        subtitle = f"({window.start.strftime('%Y-%m-%d %H:%M')} → {window.end.strftime('%Y-%m-%d %H:%M')}]"
        ax.set_title(f"{window.title}\n{subtitle}", fontsize=8)
        ax.set_xlim(0, 24)
        ax.set_ylim(y_min - margin, y_max + margin)
        ax.set_xticks(range(0, 25, 6))
        ax.grid(True, alpha=0.25)
        if legend_handles is None:
            legend_handles, legend_labels = ax.get_legend_handles_labels()

    axes[1, 0].set_xlabel("Giờ trong ngày")
    axes[1, 1].set_xlabel("Giờ trong ngày")
    axes[0, 0].set_ylabel("KPI")
    axes[1, 0].set_ylabel("KPI")
    fig.suptitle(
        f"FR-401 — {ne_id} / {cell_id}\n{kpi_name}",
        fontsize=10,
        y=0.995,
    )
    if legend_handles and legend_labels:
        fig.legend(
            legend_handles,
            legend_labels,
            loc="lower center",
            bbox_to_anchor=(0.5, 0.005),
            ncol=3,
            frameon=False,
        )
        fig.tight_layout(rect=(0, 0.065, 1, 0.93))
    else:
        fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return path


def write_temporal_profile_png(
    overlay_df: pd.DataFrame,
    *,
    ne_id: str,
    cell_id: str,
    kpi_name: str,
    output_path: str | Path,
    dpi: int = 160,
) -> Path:
    """Plot the legacy aggregated BUSY/TRANSITION/OFF_PEAK profile."""

    missing = sorted(_PROFILE_REQUIRED_COLUMNS.difference(overlay_df.columns))
    if missing:
        raise ValueError(f"Thiếu cột để vẽ biểu đồ FR-401: {', '.join(missing)}")

    selected = _filter_metric(
        overlay_df,
        ne_id=ne_id,
        cell_id=cell_id,
        kpi_name=kpi_name,
    )
    if selected.empty:
        raise ValueError("Không có dữ liệu overlay cho NE/Cell/KPI đã chọn")

    selected["mean"] = pd.to_numeric(selected["mean"], errors="coerce")
    selected["minute_of_day"] = pd.to_numeric(selected["minute_of_day"], errors="coerce")
    selected = selected.dropna(subset=["mean", "minute_of_day"])
    if selected.empty:
        raise ValueError("Dữ liệu overlay không có giá trị numeric để vẽ")

    path = _png_path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=FIGURE_SIZE_INCHES)
    for profile in ("BUSY", "TRANSITION", "OFF_PEAK"):
        subset = selected[selected["temporal_profile"] == profile].sort_values("minute_of_day")
        if subset.empty:
            continue
        subset = subset.copy()
        subset["segment"] = subset["minute_of_day"].diff().fillna(0).gt(60).cumsum()
        for _, segment in subset.groupby("segment", sort=True):
            if len(segment) == 1:
                ax.scatter(
                    segment["minute_of_day"] / 60.0,
                    segment["mean"],
                    s=12,
                    label=profile if profile not in ax.get_legend_handles_labels()[1] else None,
                )
            else:
                ax.plot(
                    segment["minute_of_day"] / 60.0,
                    segment["mean"],
                    linewidth=1.6,
                    label=profile if profile not in ax.get_legend_handles_labels()[1] else None,
                )

    ax.set_title(f"{ne_id} / {cell_id} / {kpi_name}")
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
