"""Biểu đồ SVG đơn giản để so sánh profile WEEKDAY/WEEKEND của FR-402."""

from __future__ import annotations

from html import escape
from pathlib import Path

import pandas as pd

_DAY_STYLES = {
    "WEEKDAY": ("#1f77b4", "none"),
    "WEEKEND": ("#d62728", "7,5"),
}


def write_weekly_profile_svg(
    overlay_df: pd.DataFrame,
    *,
    ne_id: str,
    cell_id: str,
    kpi_name: str,
    output_path: str | Path,
) -> Path:
    """Vẽ mean KPI theo thời điểm trong ngày, tách đường WEEKDAY/WEEKEND."""

    required = {"ne_id", "cell_id", "kpi_name", "day_type", "minute_of_day", "mean"}
    missing = sorted(required.difference(overlay_df.columns))
    if missing:
        raise ValueError(f"Thiếu cột để vẽ biểu đồ FR-402: {', '.join(missing)}")

    selected = overlay_df[
        (overlay_df["ne_id"].astype(str) == str(ne_id))
        & (overlay_df["cell_id"].astype(str) == str(cell_id))
        & (overlay_df["kpi_name"].astype(str) == str(kpi_name))
    ].copy()
    if selected.empty:
        raise ValueError("Không có dữ liệu overlay FR-402 cho NE/Cell/KPI đã chọn")

    selected["mean"] = pd.to_numeric(selected["mean"], errors="coerce")
    selected["minute_of_day"] = pd.to_numeric(
        selected["minute_of_day"], errors="coerce"
    )
    selected = selected.dropna(subset=["mean", "minute_of_day"])
    if selected.empty:
        raise ValueError("Overlay FR-402 không có giá trị số để vẽ")

    width, height = 1200, 520
    left, right, top, bottom = 80, 30, 45, 70
    plot_width = width - left - right
    plot_height = height - top - bottom
    y_min = float(selected["mean"].min())
    y_max = float(selected["mean"].max())
    if y_min == y_max:
        padding = max(abs(y_min) * 0.05, 1.0)
        y_min -= padding
        y_max += padding

    def x_coord(minute: float) -> float:
        return left + minute / 1439.0 * plot_width

    def y_coord(value: float) -> float:
        return top + (y_max - value) / (y_max - y_min) * plot_height

    lines: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{left}" y="25" font-family="Arial" font-size="18">'
        f'{escape(ne_id)} / {escape(cell_id)} / {escape(kpi_name)} - WEEKDAY và WEEKEND</text>',
        f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" '
        f'y2="{top + plot_height}" stroke="#333"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#333"/>',
    ]

    for hour in range(0, 25, 3):
        minute = min(hour * 60, 1439)
        x = x_coord(minute)
        lines.append(
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}" '
            'stroke="#e5e5e5"/>'
        )
        lines.append(
            f'<text x="{x:.1f}" y="{top + plot_height + 25}" text-anchor="middle" '
            f'font-family="Arial" font-size="12">{hour:02d}:00</text>'
        )

    for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
        value = y_min + (y_max - y_min) * fraction
        y = y_coord(value)
        lines.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" '
            'stroke="#eeeeee"/>'
        )
        lines.append(
            f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" '
            f'font-family="Arial" font-size="12">{value:.2f}</text>'
        )

    legend_x = left
    for day_type in ("WEEKDAY", "WEEKEND"):
        subset = selected[selected["day_type"] == day_type].sort_values("minute_of_day")
        color, dash = _DAY_STYLES[day_type]
        if not subset.empty:
            points = " ".join(
                f'{x_coord(float(row.minute_of_day)):.1f},{y_coord(float(row.mean)):.1f}'
                for row in subset.itertuples(index=False)
            )
            dash_attr = "" if dash == "none" else f' stroke-dasharray="{dash}"'
            lines.append(
                f'<polyline points="{points}" fill="none" stroke="{color}" '
                f'stroke-width="2"{dash_attr}/>'
            )
        lines.append(
            f'<line x1="{legend_x}" y1="{height - 20}" x2="{legend_x + 25}" '
            f'y2="{height - 20}" stroke="{color}" stroke-width="3"/>'
        )
        lines.append(
            f'<text x="{legend_x + 32}" y="{height - 16}" font-family="Arial" '
            f'font-size="12">{day_type}</text>'
        )
        legend_x += 190

    lines.append("</svg>")
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
