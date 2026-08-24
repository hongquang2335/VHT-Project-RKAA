"""Gắn cờ local spike bằng rolling median + MAD, không tự xóa record."""

from __future__ import annotations

import pandas as pd

from rkaa.domain.data_quality.models import DataQualityIssue, LocalSpikeConfig


class LocalSpikeDetector:
    """Phát hiện điểm lệch mạnh theo lịch sử của đúng NE + Cell + KPI."""

    def __init__(self, config: LocalSpikeConfig) -> None:
        self.config = config

    def detect(self, df: pd.DataFrame) -> list[DataQualityIssue]:
        if not self.config.enabled or df.empty:
            return []

        issues: list[DataQualityIssue] = []
        working = df
        # Pha 3 chỉ dùng local-spike cho KPI. Counter vẫn qua normalize,
        # duplicate, gap và range (>= 0) nhưng không bị đánh giá thống kê ở đây.
        if "is_counter" in working.columns:
            working = working.loc[~working["is_counter"].fillna(False).astype(bool)]

        for (_, _, _), group in working.groupby(
            ["ne_id", "cell_id", "kpi_name"],
            sort=False,
        ):
            group = group[group["timestamp"].notna() & group["value"].notna()].sort_values(
                "timestamp"
            )
            if len(group) <= self.config.min_samples:
                continue

            values = group["value"].astype(float)
            history = values.shift(1)
            rolling = history.rolling(
                window=self.config.window_samples,
                min_periods=self.config.min_samples,
            )
            median = rolling.median()
            mad = rolling.apply(
                lambda sample: (sample - sample.median()).abs().median(),
                raw=False,
            )
            robust_z = 0.6745 * (values - median) / mad
            spike_mask = mad.gt(0) & robust_z.abs().gt(self.config.robust_z_threshold)

            for idx in group.index[spike_mask.fillna(False)]:
                row = df.loc[idx]
                issues.append(
                    DataQualityIssue(
                        issue_type="LOCAL_SPIKE",
                        severity="WARNING",
                        row_index=int(row["_dq_row_id"]),
                        ne_id=str(row["ne_id"]),
                        cell_id=str(row["cell_id"]),
                        kpi_name=str(row["kpi_name"]),
                        timestamp=row["timestamp"],
                        period_end=row["period_end"],
                        value=row["value"],
                        detail=(
                            f"robust_z={robust_z.loc[idx]:.4f}; "
                            f"median={median.loc[idx]:.6g}; mad={mad.loc[idx]:.6g}; "
                            f"threshold={self.config.robust_z_threshold}"
                        ),
                    )
                )
        return issues
