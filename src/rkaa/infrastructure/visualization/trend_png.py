"""PNG chart adapter for FR-403 long-term trend analysis."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# FR-401/402 trước đây dùng (12, 5.2). Yêu cầu demo hiện tại giảm 50%
# theo cả chiều rộng và chiều cao; FR-403 dùng cùng kích thước mới.
FIGURE_SIZE_INCHES = (6.0, 2.6)

_COMPONENT_COLUMNS = {
    "timestamp",
    "ne_id",
    "cell_id",
    "kpi_name",
    "value",
    "trend",
}
_SUMMARY_COLUMNS = {
    "ne_id",
    "cell_id",
    "kpi_name",
    "trend_label",
    "r2",
    "trend_slope_per_day",
}


def _png_path(output_path: str | Path) -> Path:
    path = Path(output_path)
    return path if path.suffix.lower() == ".png" else path.with_suffix(".png")


def write_trend_png(
    components_df: pd.DataFrame,
    trend_df: pd.DataFrame,
    *,
    ne_id: str,
    cell_id: str,
    kpi_name: str,
    output_path: str | Path,
    dpi: int = 160,
) -> Path:
    """Plot observed/imputed KPI and STL trend for one valid NE-Cell-KPI series."""

    missing_components = sorted(_COMPONENT_COLUMNS.difference(components_df.columns))
    if missing_components:
        raise ValueError(
            "Thiếu cột để vẽ biểu đồ FR-403: " + ", ".join(missing_components)
        )
    missing_summary = sorted(_SUMMARY_COLUMNS.difference(trend_df.columns))
    if missing_summary:
        raise ValueError(
            "Thiếu cột trend summary FR-403: " + ", ".join(missing_summary)
        )

    mask = (
        (components_df["ne_id"].astype(str) == str(ne_id))
        & (components_df["cell_id"].astype(str) == str(cell_id))
        & (components_df["kpi_name"].astype(str) == str(kpi_name))
    )
    selected = components_df.loc[mask].copy()
    if selected.empty:
        raise ValueError("Không có STL components cho NE/Cell/KPI đã chọn")

    selected["timestamp"] = pd.to_datetime(
        selected["timestamp"], errors="coerce", utc=True, format="mixed"
    )
    selected["value"] = pd.to_numeric(selected["value"], errors="coerce")
    selected["trend"] = pd.to_numeric(selected["trend"], errors="coerce")
    selected = selected.dropna(subset=["timestamp", "value", "trend"]).sort_values(
        "timestamp"
    )
    if selected.empty:
        raise ValueError("STL components FR-403 không có giá trị số để vẽ")

    summary_mask = (
        (trend_df["ne_id"].astype(str) == str(ne_id))
        & (trend_df["cell_id"].astype(str) == str(cell_id))
        & (trend_df["kpi_name"].astype(str) == str(kpi_name))
    )
    summary_rows = trend_df.loc[summary_mask]
    if summary_rows.empty:
        raise ValueError("Không có trend summary cho NE/Cell/KPI đã chọn")
    summary = summary_rows.iloc[0]

    path = _png_path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=FIGURE_SIZE_INCHES)
    ax.plot(selected["timestamp"], selected["value"], linewidth=0.8, alpha=0.55, label="KPI")
    ax.plot(selected["timestamp"], selected["trend"], linewidth=1.6, label="STL trend")

    label = str(summary["trend_label"])
    r2 = float(summary["r2"])
    slope = float(summary["trend_slope_per_day"])
    ax.set_title(
        f"{ne_id} / {cell_id} / {kpi_name}\n"
        f"{label} | slope/day={slope:.4g} | R²={r2:.3f}"
    )
    ax.set_xlabel("Thời gian")
    ax.set_ylabel("KPI")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.autofmt_xdate(rotation=20)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return path
