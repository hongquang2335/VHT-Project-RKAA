"""Điều phối Data Quality Check và chuẩn hóa FR-203."""

from __future__ import annotations

from collections import Counter, defaultdict

import pandas as pd

from rkaa.domain.data_quality.duplicate_detector import DuplicateDetector
from rkaa.domain.data_quality.gap_detector import GapDetector
from rkaa.domain.data_quality.local_spike_detector import LocalSpikeDetector
from rkaa.domain.data_quality.models import (
    DataQualityConfig,
    DataQualityIssue,
    DataQualityResult,
)
from rkaa.domain.data_quality.normalizer import DataQualityNormalizer
from rkaa.domain.data_quality.range_validator import RangeValidator


_ISSUE_COLUMNS = [
    "issue_type",
    "severity",
    "row_index",
    "ne_id",
    "kpi_name",
    "timestamp",
    "value",
    "detail",
]


class DataQualityService:
    """Chạy normalize → duplicate → gap → range → local spike."""

    def __init__(self, config: DataQualityConfig) -> None:
        self.config = config

    @staticmethod
    def _issues_dataframe(issues: list[DataQualityIssue]) -> pd.DataFrame:
        rows = [
            {
                "issue_type": item.issue_type,
                "severity": item.severity,
                "row_index": item.row_index,
                "ne_id": item.ne_id,
                "kpi_name": item.kpi_name,
                "timestamp": item.timestamp,
                "value": item.value,
                "detail": item.detail,
            }
            for item in issues
        ]
        return pd.DataFrame(rows, columns=_ISSUE_COLUMNS)

    @staticmethod
    def _attach_flags(df: pd.DataFrame, issues: list[DataQualityIssue]) -> pd.DataFrame:
        by_row: dict[int, set[str]] = defaultdict(set)
        for issue in issues:
            if issue.row_index is not None:
                by_row[issue.row_index].add(issue.issue_type)

        result = df.copy()
        result["data_quality_flags"] = result["_dq_row_id"].map(
            lambda row_id: ";".join(sorted(by_row.get(int(row_id), set())))
        )
        return result

    def check(self, df: pd.DataFrame) -> DataQualityResult:
        input_records = len(df)
        normalizer = DataQualityNormalizer(self.config.normalization)
        normalized, issues = normalizer.normalize(df)

        deduplicated, duplicate_issues = DuplicateDetector(self.config.duplicate).detect(
            normalized
        )
        issues.extend(duplicate_issues)
        issues.extend(GapDetector(self.config.gap).detect(deduplicated))
        issues.extend(RangeValidator(self.config.range_validation).detect(deduplicated))
        issues.extend(LocalSpikeDetector(self.config.local_spike).detect(deduplicated))

        quality_df = self._attach_flags(deduplicated, issues)
        quality_df = quality_df.drop(columns=["_dq_row_id"]).reset_index(drop=True)
        issues_df = self._issues_dataframe(issues)

        counts = Counter(issue.issue_type for issue in issues)
        gaps_over_2h = sum(
            1
            for issue in issues
            if issue.issue_type == "GAP" and issue.severity == "WARNING"
        )
        summary: dict[str, object] = {
            "input_records": input_records,
            "output_records": len(quality_df),
            "issue_records": len(issues_df),
            "gaps_over_2h": gaps_over_2h,
            "issues_by_type": dict(sorted(counts.items())),
        }
        summary_rows = [
            {"metric": "input_records", "value": input_records},
            {"metric": "output_records", "value": len(quality_df)},
            {"metric": "issue_records", "value": len(issues_df)},
            {"metric": "gaps_over_2h", "value": gaps_over_2h},
        ]
        summary_rows.extend(
            {"metric": f"issue_{name.lower()}", "value": count}
            for name, count in sorted(counts.items())
        )
        summary_df = pd.DataFrame(summary_rows, columns=["metric", "value"])

        return DataQualityResult(
            quality_df=quality_df,
            issues_df=issues_df,
            summary_df=summary_df,
            summary=summary,
        )
