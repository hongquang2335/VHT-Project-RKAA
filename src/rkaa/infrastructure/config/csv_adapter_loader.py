"""Configuration and metric resolution for the CSV demo/source adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import pandas as pd
import yaml

from rkaa.domain.data_collector.minio_kpi_normalizer import KPIMappingItem


@dataclass(frozen=True)
class CSVSourceConfig:
    datetime_col: str
    ne_col: str
    cellname_col: str
    granularity_minutes: int
    dayfirst: bool = False
    encoding: str = "utf-8-sig"
    delimiter: str = ","
    metadata_columns: tuple[str, ...] = ()


@dataclass(frozen=True)
class MetricSpec:
    canonical_name: str
    source_candidates: tuple[str, ...]
    unit: str
    direction_preference: str
    is_counter: bool
    required: bool = False


@dataclass(frozen=True)
class DerivedMetricSpec:
    """Metric được tạo từ nhiều cột nguồn trước bước wide -> long."""

    canonical_name: str
    operation: str
    source_groups: tuple[tuple[str, ...], ...]
    unit: str
    direction_preference: str
    is_counter: bool = False
    required: bool = False


@dataclass(frozen=True)
class ResolvedDerivedMetric:
    canonical_name: str
    operation: str
    source_columns: tuple[str, ...]
    unit: str
    direction_preference: str
    is_counter: bool = False


@dataclass(frozen=True)
class AutoDiscoveryConfig:
    enabled: bool = False
    counter_prefixes: tuple[str, ...] = ("Pm.",)
    counter_suffixes: tuple[str, ...] = ("(#)",)


@dataclass(frozen=True)
class CSVAdapterConfig:
    source: CSVSourceConfig
    metrics: tuple[MetricSpec, ...]
    derived_metrics: tuple[DerivedMetricSpec, ...]
    auto_discovery: AutoDiscoveryConfig


@dataclass(frozen=True)
class MetricResolution:
    mapping: tuple[KPIMappingItem, ...]
    derived_metrics: tuple[ResolvedDerivedMetric, ...]
    missing_optional: tuple[str, ...]
    auto_discovered: tuple[str, ...]

    def source_columns(self) -> list[str]:
        """Các cột thật phải đọc từ CSV, không gồm cột dẫn xuất chưa được tạo."""

        result: list[str] = []
        seen: set[str] = set()
        for item in self.mapping:
            if item.source_column not in seen:
                result.append(item.source_column)
                seen.add(item.source_column)
        for item in self.derived_metrics:
            for source_column in item.source_columns:
                if source_column not in seen:
                    result.append(source_column)
                    seen.add(source_column)
        return result

    def normalizer_mapping(self) -> list[KPIMappingItem]:
        result = list(self.mapping)
        result.extend(
            KPIMappingItem(
                source_column=item.canonical_name,
                canonical_name=item.canonical_name,
                unit=item.unit,
                direction_preference=item.direction_preference,
                is_counter=item.is_counter,
            )
            for item in self.derived_metrics
        )
        return result


def _string(value: object, *, context: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{context} không được rỗng")
    return result


def _metric_spec(raw: object, *, index: int, is_counter: bool) -> MetricSpec:
    section = "counters" if is_counter else "kpis"
    if not isinstance(raw, dict):
        raise ValueError(f"metrics.{section}[{index}] phải là mapping")

    canonical_name = _string(
        raw.get("canonical_name"),
        context=f"metrics.{section}[{index}].canonical_name",
    )
    candidates_raw = raw.get("source_candidates")
    if candidates_raw is None and raw.get("source_column") is not None:
        candidates_raw = [raw.get("source_column")]
    if not isinstance(candidates_raw, list) or not candidates_raw:
        raise ValueError(
            f"metrics.{section}[{index}].source_candidates phải là danh sách không rỗng"
        )
    candidates = tuple(
        _string(value, context=f"metrics.{section}[{index}].source_candidates")
        for value in candidates_raw
    )

    return MetricSpec(
        canonical_name=canonical_name,
        source_candidates=candidates,
        unit=str(raw.get("unit", "")).strip(),
        direction_preference=(
            "informational"
            if is_counter
            else str(raw.get("direction_preference", "informational")).strip()
        ),
        is_counter=is_counter,
        required=bool(raw.get("required", False)),
    )


def _derived_metric_spec(raw: object, *, index: int) -> DerivedMetricSpec:
    if not isinstance(raw, dict):
        raise ValueError(f"metrics.derived_kpis[{index}] phải là mapping")
    canonical_name = _string(
        raw.get("canonical_name"),
        context=f"metrics.derived_kpis[{index}].canonical_name",
    )
    operation = _string(
        raw.get("operation", "sum"),
        context=f"metrics.derived_kpis[{index}].operation",
    ).lower()
    if operation not in {"sum"}:
        raise ValueError(
            f"metrics.derived_kpis[{index}].operation chưa hỗ trợ: {operation}"
        )

    groups_raw = raw.get("source_groups")
    if not isinstance(groups_raw, list) or not groups_raw:
        raise ValueError(
            f"metrics.derived_kpis[{index}].source_groups phải là danh sách không rỗng"
        )
    groups: list[tuple[str, ...]] = []
    for group_index, group in enumerate(groups_raw):
        if isinstance(group, str):
            group = [group]
        if not isinstance(group, list) or not group:
            raise ValueError(
                "metrics.derived_kpis"
                f"[{index}].source_groups[{group_index}] phải là alias-list không rỗng"
            )
        groups.append(
            tuple(
                _string(
                    value,
                    context=(
                        "metrics.derived_kpis"
                        f"[{index}].source_groups[{group_index}]"
                    ),
                )
                for value in group
            )
        )

    return DerivedMetricSpec(
        canonical_name=canonical_name,
        operation=operation,
        source_groups=tuple(groups),
        unit=str(raw.get("unit", "")).strip(),
        direction_preference=str(
            raw.get("direction_preference", "informational")
        ).strip(),
        required=bool(raw.get("required", False)),
    )


def load_csv_adapter_config(file_path: str | Path) -> CSVAdapterConfig:
    path = Path(file_path)
    with path.open("r", encoding="utf-8") as handle:
        raw: Any = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ValueError("CSV adapter config phải là mapping")

    source_raw = raw.get("source", {})
    if not isinstance(source_raw, dict):
        raise ValueError("source phải là mapping")
    granularity = int(source_raw.get("granularity_minutes", 60))
    if granularity <= 0:
        raise ValueError("source.granularity_minutes phải > 0")
    metadata = source_raw.get("metadata_columns", [])
    if not isinstance(metadata, list):
        raise ValueError("source.metadata_columns phải là danh sách")

    source = CSVSourceConfig(
        datetime_col=_string(source_raw.get("datetime_col"), context="source.datetime_col"),
        ne_col=_string(source_raw.get("ne_col"), context="source.ne_col"),
        cellname_col=_string(source_raw.get("cellname_col"), context="source.cellname_col"),
        granularity_minutes=granularity,
        dayfirst=bool(source_raw.get("dayfirst", False)),
        encoding=str(source_raw.get("encoding", "utf-8-sig")),
        delimiter=str(source_raw.get("delimiter", ",")),
        metadata_columns=tuple(str(value).strip() for value in metadata),
    )

    metrics_raw = raw.get("metrics", {})
    if not isinstance(metrics_raw, dict):
        raise ValueError("metrics phải là mapping")
    raw_kpis = metrics_raw.get("kpis", [])
    raw_counters = metrics_raw.get("counters", [])
    raw_derived = metrics_raw.get("derived_kpis", [])
    if not all(isinstance(value, list) for value in (raw_kpis, raw_counters, raw_derived)):
        raise ValueError("metrics.kpis/counters/derived_kpis phải là danh sách")

    specs = tuple(
        [
            *(_metric_spec(item, index=i, is_counter=False) for i, item in enumerate(raw_kpis)),
            *(
                _metric_spec(item, index=i, is_counter=True)
                for i, item in enumerate(raw_counters)
            ),
        ]
    )
    derived = tuple(
        _derived_metric_spec(item, index=i) for i, item in enumerate(raw_derived)
    )

    auto_raw = metrics_raw.get("auto_discovery", {})
    if not isinstance(auto_raw, dict):
        raise ValueError("metrics.auto_discovery phải là mapping")
    prefixes = auto_raw.get("counter_prefixes", ["Pm."])
    suffixes = auto_raw.get("counter_suffixes", ["(#)"])
    if not isinstance(prefixes, list) or not isinstance(suffixes, list):
        raise ValueError("counter_prefixes/counter_suffixes phải là danh sách")
    auto = AutoDiscoveryConfig(
        enabled=bool(auto_raw.get("enabled", False)),
        counter_prefixes=tuple(str(value) for value in prefixes),
        counter_suffixes=tuple(str(value) for value in suffixes),
    )
    return CSVAdapterConfig(
        source=source,
        metrics=specs,
        derived_metrics=derived,
        auto_discovery=auto,
    )


def resolve_csv_metric_mapping(
    available_columns: list[str],
    config: CSVAdapterConfig,
    *,
    enable_auto_discovery: bool | None = None,
) -> MetricResolution:
    available = set(available_columns)
    mapping: list[KPIMappingItem] = []
    derived: list[ResolvedDerivedMetric] = []
    missing_optional: list[str] = []
    consumed: set[str] = set()

    for spec in config.metrics:
        source_column = next(
            (candidate for candidate in spec.source_candidates if candidate in available),
            None,
        )
        if source_column is None:
            if spec.required:
                raise KeyError(
                    f"Thiếu metric bắt buộc {spec.canonical_name}; "
                    f"các alias chấp nhận: {list(spec.source_candidates)}"
                )
            missing_optional.append(spec.canonical_name)
            continue
        mapping.append(
            KPIMappingItem(
                source_column=source_column,
                canonical_name=spec.canonical_name,
                unit=spec.unit or infer_unit(source_column),
                direction_preference=spec.direction_preference,
                is_counter=spec.is_counter,
            )
        )
        consumed.add(source_column)

    for spec in config.derived_metrics:
        sources: list[str] = []
        missing_group = False
        for aliases in spec.source_groups:
            source_column = next((item for item in aliases if item in available), None)
            if source_column is None:
                missing_group = True
                break
            sources.append(source_column)
        if missing_group:
            if spec.required:
                raise KeyError(
                    f"Thiếu nguồn cho metric dẫn xuất {spec.canonical_name}; "
                    f"source_groups={spec.source_groups}"
                )
            missing_optional.append(spec.canonical_name)
            continue
        derived.append(
            ResolvedDerivedMetric(
                canonical_name=spec.canonical_name,
                operation=spec.operation,
                source_columns=tuple(sources),
                unit=spec.unit,
                direction_preference=spec.direction_preference,
                is_counter=spec.is_counter,
            )
        )
        consumed.update(sources)

    auto_enabled = config.auto_discovery.enabled
    if enable_auto_discovery is not None:
        auto_enabled = enable_auto_discovery

    auto_discovered: list[str] = []
    if auto_enabled:
        identity_and_metadata = {
            config.source.datetime_col,
            config.source.ne_col,
            config.source.cellname_col,
            *config.source.metadata_columns,
        }
        canonical_names = {item.canonical_name for item in mapping}
        canonical_names.update(item.canonical_name for item in derived)
        for column in available_columns:
            if column in identity_and_metadata or column in consumed:
                continue
            is_counter = any(
                column.startswith(prefix) for prefix in config.auto_discovery.counter_prefixes
            ) or any(column.endswith(suffix) for suffix in config.auto_discovery.counter_suffixes)
            canonical_name = column
            if canonical_name in canonical_names:
                continue
            mapping.append(
                KPIMappingItem(
                    source_column=column,
                    canonical_name=canonical_name,
                    unit=infer_unit(column),
                    direction_preference="informational",
                    is_counter=is_counter,
                )
            )
            canonical_names.add(canonical_name)
            consumed.add(column)
            auto_discovered.append(column)

    if not mapping and not derived:
        raise ValueError("Không resolve được KPI/counter nào từ CSV")
    return MetricResolution(
        mapping=tuple(mapping),
        derived_metrics=tuple(derived),
        missing_optional=tuple(missing_optional),
        auto_discovered=tuple(auto_discovered),
    )


def apply_derived_metrics(
    wide_df: pd.DataFrame,
    resolution: MetricResolution,
) -> pd.DataFrame:
    """Tạo cột dẫn xuất mà không thay đổi các cột nguồn.

    Với ``sum``, nếu mọi thành phần đều null thì kết quả vẫn null; nếu chỉ một
    thành phần null thì cũng trả null để không âm thầm biến traffic thiếu thành
    traffic một chiều.
    """

    result = wide_df.copy()
    for item in resolution.derived_metrics:
        missing = [column for column in item.source_columns if column not in result.columns]
        if missing:
            raise KeyError(
                f"Thiếu source cho derived metric {item.canonical_name}: {missing}"
            )
        numeric = result[list(item.source_columns)].apply(pd.to_numeric, errors="coerce")
        if item.operation == "sum":
            result[item.canonical_name] = numeric.sum(axis=1, min_count=len(item.source_columns))
        else:  # pragma: no cover - loader chặn operation không hỗ trợ
            raise ValueError(f"Derived operation chưa hỗ trợ: {item.operation}")
    return result


def infer_unit(column_name: str) -> str:
    match = re.search(r"\(([^()]*)\)\s*$", column_name)
    if not match:
        return ""
    unit = match.group(1).strip()
    return unit
