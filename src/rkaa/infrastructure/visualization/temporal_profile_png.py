"""PNG chart adapter for FR-401 temporal profile overlays.

Uses the non-interactive Agg backend so chart generation works on headless
Linux/Jupyter servers without a desktop environment.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

_REQUIRED_COLUMNS = {
    "ne_id",
    "cell_id",
    "kpi_name",
    "temporal_profile",
    "minute_of_day",
    "mean",
}


def _png_path(output_path: str | Path) -> Path:
    """Return an output path with a .png suffix."""

    path = Path(output_path)
    return path if path.suffix.lower() == ".png" else path.with_suffix(".png")


def write_temporal_profile_png(
    overlay_df: pd.DataFrame,
    *,
    ne_id: str,
    cell_id: str,
    kpi_name: str,
    output_path: str | Path,
    dpi: int = 160,
) -> Path:
    """Plot mean KPI by time-of-day for BUSY/TRANSITION/OFF_PEAK."""

    missing = sorted(_REQUIRED_COLUMNS.difference(overlay_df.columns))
    if missing:
        raise ValueError(f"Thiếu cột để vẽ biểu đồ FR-401: {', '.join(missing)}")

    selected = overlay_df[
        (overlay_df["ne_id"].astype(str) == str(ne_id))
        & (overlay_df["cell_id"].astype(str) == str(cell_id))
        & (overlay_df["kpi_name"].astype(str) == str(kpi_name))
    ].copy()
    if selected.empty:
        raise ValueError("Không có dữ liệu overlay cho NE/Cell/KPI đã chọn")

    selected["mean"] = pd.to_numeric(selected["mean"], errors="coerce")
    selected["minute_of_day"] = pd.to_numeric(
        selected["minute_of_day"], errors="coerce"
    )
    selected = selected.dropna(subset=["mean", "minute_of_day"])
    if selected.empty:
        raise ValueError("Dữ liệu overlay không có giá trị numeric để vẽ")

    path = _png_path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(12, 5.2))
    for profile in ("BUSY", "TRANSITION", "OFF_PEAK"):
        subset = selected[selected["temporal_profile"] == profile].sort_values(
            "minute_of_day"
        )
        if subset.empty:
            continue
        ax.plot(
            subset["minute_of_day"] / 60.0,
            subset["mean"],
            linewidth=1.6,
            label=profile,
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
