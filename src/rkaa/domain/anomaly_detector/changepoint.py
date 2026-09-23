"""FR-405 (SRS ghi trùng FR-404): PELT change-point theo từng NE + Cell + KPI."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class ChangePointConfig:
    penalty_scale: float = 8.0
    minimum_segment_points: int = 12
    detect_variance: bool = True
    search_step_points: int = 2


class ChangePointDetector:
    """PELT trên STL trend (level) và residual² (variance).

    Input components đến từ FR-403 nên daily seasonality đã được tách trước khi
    tìm level/variance change, tránh báo change-point ở mỗi chu kỳ ngày/đêm.
    """

    def __init__(self, config: ChangePointConfig | None = None) -> None:
        self.config = config or ChangePointConfig()
        if self.config.penalty_scale <= 0:
            raise ValueError("penalty_scale phải > 0")
        if self.config.minimum_segment_points < 2:
            raise ValueError("minimum_segment_points phải >= 2")
        if self.config.search_step_points < 1:
            raise ValueError("search_step_points phải >= 1")

    @staticmethod
    def _standardize(values: np.ndarray) -> np.ndarray:
        std = float(np.std(values))
        if std <= 1e-12:
            return np.zeros_like(values, dtype=float)
        return (values - float(np.mean(values))) / std

    @staticmethod
    def _segment_cost(prefix: np.ndarray, prefix_sq: np.ndarray, start: int, end: int) -> float:
        n = end - start
        if n <= 0:
            return math.inf
        total = prefix[end] - prefix[start]
        total_sq = prefix_sq[end] - prefix_sq[start]
        return max(0.0, float(total_sq - total * total / n))

    def _pelt(self, values: np.ndarray) -> list[int]:
        """PELT với squared-error cost; trả index bắt đầu segment mới.

        ``search_step_points`` coarsen chuỗi bằng block-mean trước PELT. Với
        step=2, sai số định vị tối đa do lưới là một granularity period, vẫn
        nằm trong acceptance <= 2 periods của SRS nhưng giảm mạnh chi phí demo.
        """

        raw = np.asarray(values, dtype=float)
        step = self.config.search_step_points
        if step > 1:
            block_count = int(math.ceil(len(raw) / step))
            reduced = np.array(
                [float(np.mean(raw[i * step : min((i + 1) * step, len(raw))]))
                 for i in range(block_count)],
                dtype=float,
            )
        else:
            reduced = raw

        y = self._standardize(reduced)
        n = len(y)
        min_size = max(2, int(math.ceil(self.config.minimum_segment_points / step)))
        if n < min_size * 2 or float(np.std(y)) <= 1e-12:
            return []

        penalty = self.config.penalty_scale * math.log(max(n, 2))
        prefix = np.concatenate(([0.0], np.cumsum(y)))
        prefix_sq = np.concatenate(([0.0], np.cumsum(y * y)))
        best_cost = np.full(n + 1, np.inf, dtype=float)
        best_cost[0] = -penalty
        previous = np.full(n + 1, -1, dtype=int)
        candidates = np.array([0], dtype=int)

        for endpoint in range(min_size, n + 1):
            eligible_mask = (endpoint - candidates) >= min_size
            starts = candidates[eligible_mask]
            if starts.size:
                finite = np.isfinite(best_cost[starts])
                starts = starts[finite]
            if starts.size:
                lengths = endpoint - starts
                totals = prefix[endpoint] - prefix[starts]
                totals_sq = prefix_sq[endpoint] - prefix_sq[starts]
                segment_costs = np.maximum(
                    0.0,
                    totals_sq - (totals * totals) / lengths,
                )
                objectives = best_cost[starts] + segment_costs + penalty
                winner = int(np.argmin(objectives))
                best_start = int(starts[winner])
                best_cost[endpoint] = float(objectives[winner])
                previous[endpoint] = best_start

                # PELT pruning. +penalty giữ pruning bảo thủ và ổn định khi
                # cost gần nhau, đồng thời vẫn loại phần lớn candidate cũ.
                bounds = best_cost[starts] + segment_costs
                keep_starts = starts[bounds <= best_cost[endpoint] + penalty]
                too_new = candidates[~eligible_mask]
                candidates = np.unique(np.concatenate((too_new, keep_starts)))

            if np.isfinite(best_cost[endpoint]):
                candidates = np.append(candidates, endpoint)

        if previous[n] < 0:
            return []
        breakpoints: list[int] = []
        cursor = n
        while cursor > 0 and previous[cursor] >= 0:
            segment_start = int(previous[cursor])
            if segment_start > 0:
                breakpoints.append(min(len(raw) - 1, segment_start * step))
            cursor = segment_start
        return sorted(set(breakpoints))

    def detect(self, components_df: pd.DataFrame) -> pd.DataFrame:
        required = {
            "timestamp",
            "ne_id",
            "cell_id",
            "kpi_name",
            "trend",
            "residual",
        }
        missing = sorted(required.difference(components_df.columns))
        if missing:
            raise ValueError(f"Thiếu cột cho change-point FR-405: {', '.join(missing)}")

        rows: list[dict[str, object]] = []
        keys = ["ne_id", "cell_id", "kpi_name"]
        for group_keys, group in components_df.groupby(keys, dropna=False, sort=True):
            ne_id, cell_id, kpi_name = (str(item) for item in group_keys)
            ordered = group.sort_values("timestamp").reset_index(drop=True)
            timestamps = pd.to_datetime(ordered["timestamp"], utc=True, errors="coerce")
            trend = pd.to_numeric(ordered["trend"], errors="coerce").to_numpy(dtype=float)
            residual = pd.to_numeric(ordered["residual"], errors="coerce").to_numpy(dtype=float)
            if np.isnan(trend).any() or np.isnan(residual).any() or timestamps.isna().any():
                continue

            detected: dict[int, set[str]] = {}
            for index in self._pelt(trend):
                detected.setdefault(index, set()).add("LEVEL")
            if self.config.detect_variance:
                variance_signal = residual * residual
                for index in self._pelt(variance_signal):
                    detected.setdefault(index, set()).add("VARIANCE")

            for index, kinds in sorted(detected.items()):
                left_start = max(0, index - self.config.minimum_segment_points)
                right_end = min(len(trend), index + self.config.minimum_segment_points)
                before = trend[left_start:index]
                after = trend[index:right_end]
                before_resid = residual[left_start:index]
                after_resid = residual[index:right_end]
                rows.append(
                    {
                        "ne_id": ne_id,
                        "cell_id": cell_id,
                        "kpi_name": kpi_name,
                        "change_index": index,
                        "change_timestamp": timestamps.iloc[index],
                        "change_type": "+".join(sorted(kinds)),
                        "level_before": float(np.mean(before)) if len(before) else math.nan,
                        "level_after": float(np.mean(after)) if len(after) else math.nan,
                        "level_delta": (
                            float(np.mean(after) - np.mean(before))
                            if len(before) and len(after)
                            else math.nan
                        ),
                        "variance_before": (
                            float(np.var(before_resid)) if len(before_resid) else math.nan
                        ),
                        "variance_after": (
                            float(np.var(after_resid)) if len(after_resid) else math.nan
                        ),
                    }
                )
        return pd.DataFrame(rows)
