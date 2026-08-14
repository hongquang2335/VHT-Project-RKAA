"""Sinh biểu đồ SVG thể hiện delta và threshold FR-303."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Mapping

from rkaa.domain.threshold_manager import KpiThresholdPolicy, ThresholdMode


def _threshold_points(policy: KpiThresholdPolicy, mode: ThresholdMode) -> list[tuple[float, str]]:
    points: list[tuple[float, str]] = []
    for sign, direction_name, thresholds in (
        (1.0, "tăng", policy.increase),
        (-1.0, "giảm", policy.decrease),
    ):
        for level_name, level in (("warning", thresholds.warning), ("critical", thresholds.critical)):
            if level is not None and level.mode is mode:
                points.append((sign * level.value, f"{direction_name} {level_name}"))
    return points


def _axis_svg(
    *,
    y: int,
    label: str,
    observed: float,
    threshold_points: list[tuple[float, str]],
) -> str:
    width = 760
    x0 = 120
    center = x0 + width / 2
    magnitudes = [abs(observed), *[abs(value) for value, _ in threshold_points], 1.0]
    limit = max(magnitudes) * 1.2

    def scale(value: float) -> float:
        return center + value / limit * (width / 2)

    parts = [
        f'<text x="40" y="{y - 18}" font-size="16">{escape(label)}</text>',
        f'<line x1="{x0}" y1="{y}" x2="{x0 + width}" y2="{y}" stroke="black"/>',
        f'<line x1="{center:.1f}" y1="{y - 10}" x2="{center:.1f}" y2="{y + 10}" stroke="black"/>',
        f'<text x="{center - 5:.1f}" y="{y + 28}" font-size="12">0</text>',
    ]
    for value, name in threshold_points:
        x = scale(value)
        parts.append(
            f'<line x1="{x:.1f}" y1="{y - 22}" x2="{x:.1f}" y2="{y + 22}" '
            'stroke="black" stroke-dasharray="4,4"/>'
        )
        parts.append(
            f'<text x="{x + 4:.1f}" y="{y - 28}" font-size="11">'
            f'{escape(name)}={value:g}</text>'
        )

    observed_x = scale(observed)
    parts.append(
        f'<circle cx="{observed_x:.1f}" cy="{y}" r="7" fill="none" stroke="black" stroke-width="2"/>'
    )
    parts.append(
        f'<text x="{observed_x + 10:.1f}" y="{y + 20}" font-size="12">delta={observed:g}</text>'
    )
    return "\n".join(parts)


def write_impact_threshold_svg(
    row: Mapping[str, object],
    policy: KpiThresholdPolicy,
    output_path: str | Path,
) -> Path:
    """Vẽ delta của một dòng FR-302 cùng các ngưỡng tăng/giảm đã cấu hình."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    delta_absolute = float(row["delta_mean"])
    delta_percent = float(row["delta_percent"])
    title = (
        f"FR-303 Threshold - {policy.kpi_name} | "
        f"{row.get('ne_id', '-')} / {row.get('cell_id', '-')} | "
        f"{row.get('temporal_profile', '-')} / {row.get('day_type', '-')}"
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="360" viewBox="0 0 960 360">
<rect x="0" y="0" width="960" height="360" fill="white" stroke="black"/>
<text x="40" y="45" font-size="22" font-weight="bold">{escape(title)}</text>
<text x="40" y="75" font-size="13">Ngưỡng được đọc từ cấu hình FR-303; điểm tròn là delta của KPI.</text>
{_axis_svg(y=155, label="Delta tuyệt đối", observed=delta_absolute, threshold_points=_threshold_points(policy, ThresholdMode.ABSOLUTE))}
{_axis_svg(y=285, label="Delta phần trăm (%)", observed=delta_percent, threshold_points=_threshold_points(policy, ThresholdMode.PERCENTAGE))}
</svg>'''
    path.write_text(svg, encoding="utf-8")
    return path
