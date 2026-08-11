"""Phát hiện khoảng trống dữ liệu theo từng NE + Cell + KPI."""

from __future__ import annotations

import pandas as pd

from rkaa.domain.data_quality.models import DataQualityIssue, GapConfig


class GapDetector:
    def __init__(self, config: GapConfig) -> None:
        self.config = config

    def detect(self, df: pd.DataFrame) -> list[DataQualityIssue]:
        if not self.config.enabled or df.empty:
            return []

        expected = pd.Timedelta(minutes=self.config.expected_interval_minutes)
        warning = pd.Timedelta(minutes=self.config.warning_threshold_minutes)
        issues: list[DataQualityIssue] = []

        for (_, _, _), group in df.groupby(
            ["ne_id", "cell_id", "kpi_name"],
            sort=False,
        ):
            valid = group[group["timestamp"].notna()].sort_values("timestamp")
            if len(valid) < 2:
                continue
            previous = valid["timestamp"].shift(1)
            deltas = valid["timestamp"] - previous

            for idx in valid.index[deltas > expected]:
                row = df.loc[idx]
                delta = deltas.loc[idx]
                previous_ts = previous.loc[idx]
                missing_periods = max(int(delta / expected) - 1, 1)
                severity = "WARNING" if delta > warning else "INFO"
                issues.append(
                    DataQualityIssue(
                        issue_type="GAP",
                        severity=severity,
                        row_index=int(row["_dq_row_id"]),
                        ne_id=str(row["ne_id"]),
                        cell_id=str(row["cell_id"]),
                        kpi_name=str(row["kpi_name"]),
                        timestamp=row["timestamp"],
                        period_end=row["period_end"],
                        value=row["value"],
                        detail=(
                            f"previous={previous_ts}; current={row['timestamp']}; "
                            f"duration_minutes={delta.total_seconds()/60:.0f}; "
                            f"missing_periods={missing_periods}"
                        ),
                    )
                )
        return issues
