"""Vectorized data-quality fast path for the CSV demo adapter only.

This module intentionally does not replace FR-203 core.  It exists so the
hourly demo source can be prepared quickly before exercising the shared
FR-201/FR-401/FR-402 core pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from rkaa.domain.data_quality.models import DataQualityConfig


KEY_COLUMNS = ["timestamp", "period_end", "ne_id", "cell_id", "kpi_name"]
ISSUE_COLUMNS = [
    "issue_type",
    "severity",
    "row_index",
    "timestamp",
    "period_end",
    "ne_id",
    "cell_id",
    "kpi_name",
    "value",
    "detail",
]
REQUIRED_COLUMNS = ["timestamp", "period_end", "ne_id", "cell_id", "kpi_name", "value"]


@dataclass(frozen=True)
class DemoQualityResult:
    quality_df: pd.DataFrame
    issues_df: pd.DataFrame
    summary_df: pd.DataFrame
    summary: dict[str, object]


def _issue_frame(df: pd.DataFrame, mask: pd.Series, *, issue_type: str, severity: str, detail: pd.Series | str) -> pd.DataFrame:
    if not bool(mask.any()):
        return pd.DataFrame(columns=ISSUE_COLUMNS)
    selected = df.loc[mask]
    if isinstance(detail, str):
        details = pd.Series(detail, index=selected.index, dtype="object")
    else:
        details = detail.loc[selected.index].astype("object")
    return pd.DataFrame(
        {
            "issue_type": issue_type,
            "severity": severity,
            "row_index": selected["_dq_row_id"].astype("int64").to_numpy(),
            "timestamp": selected["timestamp"].to_numpy(),
            "period_end": selected["period_end"].to_numpy(),
            "ne_id": selected["ne_id"].astype(str).to_numpy(),
            "cell_id": selected["cell_id"].astype(str).to_numpy(),
            "kpi_name": selected["kpi_name"].astype(str).to_numpy(),
            "value": selected["value"].to_numpy(),
            "detail": details.to_numpy(),
        },
        columns=ISSUE_COLUMNS,
    )


def _normalize(df: pd.DataFrame) -> tuple[pd.DataFrame, list[pd.DataFrame]]:
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"CSV demo quality thiếu cột bắt buộc: {missing}")

    working = df.copy()
    working["_dq_row_id"] = np.arange(len(working), dtype=np.int64)
    issues: list[pd.DataFrame] = []

    for column in ("ne_id", "cell_id", "kpi_name", "unit", "quality_flag"):
        if column in working.columns:
            working[column] = working[column].astype("string").str.strip()

    original_timestamp = working["timestamp"].copy()
    working["timestamp"] = pd.to_datetime(original_timestamp, errors="coerce", utc=True)
    invalid_ts = working["timestamp"].isna() & original_timestamp.notna()
    issues.append(
        _issue_frame(
            working,
            invalid_ts,
            issue_type="INVALID_TIMESTAMP",
            severity="ERROR",
            detail="timestamp không parse được",
        )
    )

    original_period_end = working["period_end"].copy()
    working["period_end"] = pd.to_datetime(original_period_end, errors="coerce", utc=True)
    invalid_end = working["period_end"].isna() & original_period_end.notna()
    issues.append(
        _issue_frame(
            working,
            invalid_end,
            issue_type="INVALID_PERIOD_END",
            severity="ERROR",
            detail="period_end không parse được",
        )
    )

    original_value = working["value"].copy()
    numeric_value = pd.to_numeric(original_value, errors="coerce")
    non_numeric = original_value.notna() & numeric_value.isna()
    working["value"] = numeric_value
    issues.append(
        _issue_frame(
            working,
            non_numeric,
            issue_type="NON_NUMERIC_VALUE",
            severity="ERROR",
            detail="value không chuyển được sang số",
        )
    )

    if "is_counter" in working.columns:
        raw = working["is_counter"]
        if not pd.api.types.is_bool_dtype(raw.dtype):
            normalized = raw.astype("string").str.strip().str.lower().fillna("")
            truthy = {"1", "true", "yes", "y"}
            falsy = {"0", "false", "no", "n", "", "<na>", "nan", "none"}
            unknown = ~normalized.isin(truthy | falsy)
            if bool(unknown.any()):
                raise ValueError(
                    "is_counter có giá trị không hợp lệ: "
                    + str(sorted(set(normalized.loc[unknown].astype(str))))
                )
            working["is_counter"] = normalized.isin(truthy)
        else:
            working["is_counter"] = raw.fillna(False).astype(bool)

    working = working.sort_values(
        ["ne_id", "cell_id", "kpi_name", "timestamp", "period_end", "_dq_row_id"],
        na_position="last",
        kind="stable",
    ).reset_index(drop=True)
    return working, issues


def _deduplicate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    duplicate_mask = df.duplicated(KEY_COLUMNS, keep=False)
    if not bool(duplicate_mask.any()):
        return df, pd.DataFrame(columns=ISSUE_COLUMNS)

    dup = df.loc[duplicate_mask].copy()
    # nunique(dropna=False)==1 means the duplicate key has one exact value.
    value_counts = dup.groupby(KEY_COLUMNS, dropna=False, sort=False)["value"].transform(
        lambda values: values.nunique(dropna=False)
    )
    exact_group = value_counts.eq(1)
    exact_duplicate = exact_group & dup.duplicated(KEY_COLUMNS, keep="first")
    conflict = ~exact_group

    issue_parts: list[pd.DataFrame] = []
    issue_parts.append(
        _issue_frame(
            dup,
            exact_duplicate,
            issue_type="DUPLICATE_EXACT",
            severity="INFO",
            detail="bản ghi duplicate exact; giữ record xuất hiện đầu tiên",
        )
    )
    issue_parts.append(
        _issue_frame(
            dup,
            conflict,
            issue_type="DUPLICATE_CONFLICT",
            severity="ERROR",
            detail="cùng key nhưng value khác nhau",
        )
    )
    non_empty = [part for part in issue_parts if not part.empty]
    issues = (
        pd.concat(non_empty, ignore_index=True)
        if non_empty
        else pd.DataFrame(columns=ISSUE_COLUMNS)
    )
    drop_row_ids = set(dup.loc[exact_duplicate, "_dq_row_id"].astype(int).tolist())
    if drop_row_ids:
        df = df.loc[~df["_dq_row_id"].isin(drop_row_ids)].reset_index(drop=True)
    return df, issues


def _gap_issues(df: pd.DataFrame, config: DataQualityConfig) -> pd.DataFrame:
    if not config.gap.enabled or df.empty:
        return pd.DataFrame(columns=ISSUE_COLUMNS)

    group_columns = ["ne_id", "cell_id", "kpi_name"]
    previous = df.groupby(group_columns, sort=False)["timestamp"].shift(1)
    delta = df["timestamp"] - previous
    expected = pd.Timedelta(minutes=config.gap.expected_interval_minutes)
    warning = pd.Timedelta(minutes=config.gap.warning_threshold_minutes)
    mask = df["timestamp"].notna() & previous.notna() & delta.gt(expected)
    if not bool(mask.any()):
        return pd.DataFrame(columns=ISSUE_COLUMNS)

    selected = df.loc[mask]
    selected_delta = delta.loc[mask]
    selected_previous = previous.loc[mask]
    missing_periods = (selected_delta / expected).astype(int).sub(1).clip(lower=1)
    severity = np.where(selected_delta.gt(warning), "WARNING", "INFO")
    detail = pd.Series(
        [
            f"previous={prev}; current={curr}; duration_minutes={minutes:.0f}; missing_periods={missing}"
            for prev, curr, minutes, missing in zip(
                selected_previous,
                selected["timestamp"],
                selected_delta.dt.total_seconds().div(60),
                missing_periods,
                strict=False,
            )
        ],
        index=selected.index,
    )
    result = _issue_frame(
        df,
        mask,
        issue_type="GAP",
        severity="INFO",  # overwritten below per-row
        detail=detail,
    )
    result["severity"] = severity
    return result


def _range_issues(df: pd.DataFrame, config: DataQualityConfig) -> pd.DataFrame:
    if not config.range_validation.enabled or df.empty:
        return pd.DataFrame(columns=ISSUE_COLUMNS)

    parts: list[pd.DataFrame] = []
    for kpi_name, rule in config.range_validation.rules.items():
        base = df["kpi_name"].eq(kpi_name) & df["value"].notna()
        if not bool(base.any()):
            continue
        mask = pd.Series(False, index=df.index)
        detail = pd.Series("", index=df.index, dtype="object")
        if rule.min_value is not None:
            low = base & df["value"].lt(rule.min_value)
            mask |= low
            detail.loc[low] = df.loc[low, "value"].map(
                lambda value: f"value={value} < min={rule.min_value}"
            )
        if rule.max_value is not None:
            high = base & df["value"].gt(rule.max_value)
            mask |= high
            detail.loc[high] = df.loc[high, "value"].map(
                lambda value: f"value={value} > max={rule.max_value}"
            )
        parts.append(
            _issue_frame(
                df,
                mask,
                issue_type="INVALID_RANGE",
                severity="ERROR",
                detail=detail,
            )
        )

    if "is_counter" in df.columns and config.range_validation.counter_min_value is not None:
        counter_mask = (
            df["is_counter"].fillna(False).astype(bool)
            & df["value"].notna()
            & df["value"].lt(config.range_validation.counter_min_value)
        )
        parts.append(
            _issue_frame(
                df,
                counter_mask,
                issue_type="INVALID_RANGE",
                severity="ERROR",
                detail="counter dưới minimum",
            )
        )

    non_empty = [part for part in parts if not part.empty]
    return pd.concat(non_empty, ignore_index=True) if non_empty else pd.DataFrame(columns=ISSUE_COLUMNS)


def fast_check_csv_demo(df: pd.DataFrame, config: DataQualityConfig) -> DemoQualityResult:
    """Run vectorized DQ for adapter demo while preserving core output contract."""

    if config.local_spike.enabled:
        raise ValueError(
            "CSV demo fast-path yêu cầu local_spike.enabled=false; "
            "dùng FR-203 core nếu cần rolling local-spike đầy đủ."
        )

    input_records = len(df)
    working, issue_parts = _normalize(df)
    if config.duplicate.enabled:
        working, duplicate_issues = _deduplicate(working)
        issue_parts.append(duplicate_issues)
    issue_parts.append(_gap_issues(working, config))
    issue_parts.append(_range_issues(working, config))

    non_empty = [part for part in issue_parts if not part.empty]
    issues = pd.concat(non_empty, ignore_index=True) if non_empty else pd.DataFrame(columns=ISSUE_COLUMNS)

    quality = working.copy()
    if issues.empty:
        quality["data_quality_flags"] = ""
    else:
        row_flags = (
            issues.dropna(subset=["row_index"])
            .assign(row_index=lambda frame: frame["row_index"].astype("int64"))
            .groupby("row_index", sort=False)["issue_type"]
            .agg(lambda values: ";".join(sorted(set(values))))
        )
        quality["data_quality_flags"] = quality["_dq_row_id"].map(row_flags).fillna("")
    quality = quality.drop(columns=["_dq_row_id"]).reset_index(drop=True)

    counts = issues["issue_type"].value_counts().sort_index().to_dict() if not issues.empty else {}
    gaps_over_2h = int(
        ((issues["issue_type"] == "GAP") & (issues["severity"] == "WARNING")).sum()
    ) if not issues.empty else 0
    summary: dict[str, object] = {
        "input_records": input_records,
        "output_records": len(quality),
        "issue_records": len(issues),
        "gaps_over_2h": gaps_over_2h,
        "issues_by_type": {str(key): int(value) for key, value in counts.items()},
        "demo_fast_path": True,
        "local_spike": "DISABLED_DEMO_FAST_PATH",
    }
    rows = [
        {"metric": "input_records", "value": input_records},
        {"metric": "output_records", "value": len(quality)},
        {"metric": "issue_records", "value": len(issues)},
        {"metric": "gaps_over_2h", "value": gaps_over_2h},
    ]
    rows.extend(
        {"metric": f"issue_{name.lower()}", "value": int(count)}
        for name, count in counts.items()
    )
    summary_df = pd.DataFrame(rows, columns=["metric", "value"])
    return DemoQualityResult(quality, issues, summary_df, summary)
