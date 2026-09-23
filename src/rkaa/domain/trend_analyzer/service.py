"""FR-403/FR-404: STL trend analysis cho từng KPI của từng cặp NE + Cell hợp lệ."""

from __future__ import annotations

import math
from collections.abc import Mapping

import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL

from rkaa.domain.trend_analyzer.eligibility import ValidNECellSelector
from rkaa.domain.trend_analyzer.models import TrendAnalysisConfig, TrendAnalysisResult

_REQUIRED = {"timestamp", "ne_id", "cell_id", "kpi_name", "value"}


class TrendAnalyzer:
    """STL -> linear slope/R² -> trend label, tách riêng theo NE + Cell + KPI."""

    def __init__(self, config: TrendAnalysisConfig) -> None:
        if config.granularity_minutes <= 0:
            raise ValueError("granularity_minutes phải > 0")
        if config.analysis_window_days < 1:
            raise ValueError("analysis_window_days phải >= 1")
        if config.minimum_clean_days < 1:
            raise ValueError("minimum_clean_days phải >= 1")
        if config.seasonal_periods < 2:
            raise ValueError("seasonal_periods phải >= 2")
        if not 0 < config.minimum_pair_completeness <= 1:
            raise ValueError("minimum_pair_completeness phải nằm trong (0, 1]")
        if not 0 < config.minimum_series_completeness <= 1:
            raise ValueError("minimum_series_completeness phải nằm trong (0, 1]")
        self.config = config

    @staticmethod
    def infer_percent_direction(
        values: pd.Series,
        *,
        edge_margin: float,
    ) -> tuple[str, float, str, float]:
        """FR-404: suy luận chiều tốt/xấu cho KPI % từ thống kê gần biên.

        Trả về ``(direction, confidence, nearest_edge, edge_distance)``.
        ``nearest_edge`` là ``100``, ``0`` hoặc ``MIDDLE``. Vùng giữa không bị
        ép semantic để tránh tự suy diễn tốt/xấu khi thống kê không đủ rõ.
        """

        clean = pd.to_numeric(values, errors="coerce").dropna()
        if clean.empty:
            return "informational", 0.0, "MIDDLE", math.nan
        mean = float(clean.mean())
        p05 = float(clean.quantile(0.05))
        p95 = float(clean.quantile(0.95))
        edge_margin = float(edge_margin)
        if not 0 < edge_margin < 50:
            raise ValueError("percent_edge_margin phải nằm trong (0, 50)")

        upper_start = 100.0 - edge_margin
        lower_end = edge_margin
        distance_to_zero = abs(mean)
        distance_to_hundred = abs(100.0 - mean)
        if mean >= upper_start and p05 >= 50.0:
            confidence = min(1.0, max(0.0, (mean - upper_start) / edge_margin))
            return "higher_is_better", confidence, "100", distance_to_hundred
        if mean <= lower_end and p95 <= 50.0:
            confidence = min(1.0, max(0.0, (lower_end - mean) / edge_margin))
            return "lower_is_better", confidence, "0", distance_to_zero
        return (
            "informational",
            0.0,
            "MIDDLE",
            min(distance_to_zero, distance_to_hundred),
        )

    def analyze(
        self,
        df: pd.DataFrame,
        *,
        direction_preferences: Mapping[str, str] | None = None,
    ) -> TrendAnalysisResult:
        missing = sorted(_REQUIRED.difference(df.columns))
        if missing:
            raise ValueError(f"Thiếu cột bắt buộc cho FR-403/404: {', '.join(missing)}")

        selector = ValidNECellSelector(
            granularity_minutes=self.config.granularity_minutes,
            minimum_clean_days=self.config.minimum_clean_days,
            minimum_completeness=self.config.minimum_pair_completeness,
        )
        pair_validity = selector.evaluate(df)
        valid_df = selector.filter_valid(df, pair_validity)
        preferences = dict(direction_preferences or {})

        trend_rows: list[dict[str, object]] = []
        component_parts: list[pd.DataFrame] = []
        group_keys = ["ne_id", "cell_id", "kpi_name"]
        for keys, group in valid_df.groupby(group_keys, dropna=False, sort=True):
            ne_id, cell_id, kpi_name = (str(item) for item in keys)
            summary, components = self._analyze_series(
                group,
                ne_id=ne_id,
                cell_id=cell_id,
                kpi_name=kpi_name,
                direction_preference=preferences.get(kpi_name, "informational"),
            )
            trend_rows.append(summary)
            if components is not None:
                component_parts.append(components)

        trend_df = pd.DataFrame(trend_rows)
        components_df = (
            pd.concat(component_parts, ignore_index=True)
            if component_parts
            else pd.DataFrame(
                columns=[
                    "timestamp",
                    "ne_id",
                    "cell_id",
                    "kpi_name",
                    "value",
                    "trend",
                    "seasonal",
                    "residual",
                    "was_imputed",
                ]
            )
        )
        return TrendAnalysisResult(
            pair_validity_df=pair_validity,
            trend_df=trend_df,
            components_df=components_df,
        )

    def _analyze_series(
        self,
        group: pd.DataFrame,
        *,
        ne_id: str,
        cell_id: str,
        kpi_name: str,
        direction_preference: str,
    ) -> tuple[dict[str, object], pd.DataFrame | None]:
        unit = ""
        if "unit" in group.columns:
            units = group["unit"].dropna().astype(str).str.strip()
            if not units.empty:
                unit = units.iloc[0]

        series = group[["timestamp", "value"]].copy()
        series["timestamp"] = pd.to_datetime(
            series["timestamp"], errors="coerce", utc=True, format="mixed"
        )
        series["value"] = pd.to_numeric(series["value"], errors="coerce")
        series = series.dropna(subset=["timestamp"])
        series = series.groupby("timestamp", as_index=False)["value"].mean()
        series = series.sort_values("timestamp")

        # FR-403/404: chỉ phân tích cửa sổ lịch sử gần nhất theo cấu hình
        # (mặc định 30 ngày theo SRS), thay vì để lịch sử rất cũ chi phối trend.
        if not series.empty:
            analysis_end = series["timestamp"].iloc[-1]
            analysis_start = analysis_end - pd.Timedelta(days=self.config.analysis_window_days)
            series = series[series["timestamp"] > analysis_start].copy()
        else:
            analysis_start = pd.NaT
            analysis_end = pd.NaT

        base = {
            "ne_id": ne_id,
            "cell_id": cell_id,
            "kpi_name": kpi_name,
            "unit": unit,
            "analysis_window_days": self.config.analysis_window_days,
            "analysis_start": analysis_start,
            "analysis_end": analysis_end,
        }
        if series.empty:
            return {**base, "series_eligible": False, "eligibility_reason": "NO_DATA"}, None

        start = series["timestamp"].iloc[0]
        end = series["timestamp"].iloc[-1]
        freq = pd.Timedelta(minutes=self.config.granularity_minutes)
        index = pd.date_range(start=start, end=end, freq=freq, tz="UTC")
        observed = series.set_index("timestamp")["value"].reindex(index)
        observed_count = int(observed.notna().sum())
        expected_count = int(len(observed))
        completeness = observed_count / expected_count if expected_count else 0.0
        clean_day_count = int(series.loc[series["value"].notna(), "timestamp"].dt.date.nunique())

        reason = ""
        if clean_day_count < self.config.minimum_clean_days:
            reason = "INSUFFICIENT_DAYS"
        elif completeness < self.config.minimum_series_completeness:
            reason = "LOW_COMPLETENESS"
        elif expected_count < self.config.seasonal_periods * 2:
            reason = "INSUFFICIENT_SEASONAL_CYCLES"

        if reason:
            return (
                {
                    **base,
                    "series_eligible": False,
                    "eligibility_reason": reason,
                    "observed_points": observed_count,
                    "expected_points": expected_count,
                    "series_completeness": completeness,
                    "clean_day_count": clean_day_count,
                },
                None,
            )

        filled = observed.interpolate(method="time", limit_direction="both")
        imputed = observed.isna()
        stl = STL(
            filled.to_numpy(dtype=float),
            period=self.config.seasonal_periods,
            robust=True,
        ).fit()
        trend = np.asarray(stl.trend, dtype=float)
        seasonal = np.asarray(stl.seasonal, dtype=float)
        residual = np.asarray(stl.resid, dtype=float)
        values = filled.to_numpy(dtype=float)

        x_days = np.arange(expected_count, dtype=float) * (
            self.config.granularity_minutes / 1440.0
        )
        slope, intercept = np.polyfit(x_days, trend, deg=1)
        fitted = intercept + slope * x_days
        ss_res = float(np.square(trend - fitted).sum())
        ss_tot = float(np.square(trend - float(trend.mean())).sum())
        r2 = 1.0 if ss_tot <= 1e-12 and ss_res <= 1e-12 else 0.0
        if ss_tot > 1e-12:
            r2 = max(0.0, min(1.0, 1.0 - ss_res / ss_tot))

        level = max(abs(float(np.median(trend))), 1e-9)
        relative_slope = float(slope) / level
        raw_direction = "stable"
        if abs(relative_slope) > self.config.stable_relative_slope_per_day:
            raw_direction = "increasing" if slope > 0 else "decreasing"

        residual_ratio = float(np.std(residual)) / max(float(np.std(values)), 1e-9)
        volatility_flag = residual_ratio >= self.config.volatile_residual_ratio

        configured_preference = str(
            direction_preference or "informational"
        ).strip().lower()
        if configured_preference not in {
            "higher_is_better",
            "lower_is_better",
            "informational",
        }:
            configured_preference = "informational"

        fr404_applicable = unit.strip() == "%"
        fr404_direction = "not_applicable"
        fr404_confidence = math.nan
        fr404_nearest_edge = "NOT_APPLICABLE"
        fr404_edge_distance = math.nan
        if fr404_applicable:
            (
                fr404_direction,
                fr404_confidence,
                fr404_nearest_edge,
                fr404_edge_distance,
            ) = self.infer_percent_direction(
                pd.Series(values), edge_margin=self.config.percent_edge_margin
            )

        # Mapping cấu hình (nếu có) vẫn là authority. FR-404 tự động chỉ được
        # dùng khi KPI chưa có semantic tốt/xấu rõ ràng trong mapping.
        preference = configured_preference
        preference_source = "configured"
        if preference == "informational" and fr404_applicable:
            preference = fr404_direction
            preference_source = "fr404_percent_statistics"

        confident = r2 >= self.config.r2_confident_threshold
        if not confident:
            label = "unclear"
        elif volatility_flag:
            label = "volatile"
        elif raw_direction == "stable":
            label = "stable"
        elif preference == "higher_is_better":
            label = "improving" if raw_direction == "increasing" else "degrading"
        elif preference == "lower_is_better":
            label = "improving" if raw_direction == "decreasing" else "degrading"
        else:
            label = raw_direction

        summary = {
            **base,
            "series_eligible": True,
            "eligibility_reason": "",
            "observed_points": observed_count,
            "expected_points": expected_count,
            "imputed_points": int(imputed.sum()),
            "series_completeness": completeness,
            "clean_day_count": clean_day_count,
            "mean": float(np.mean(values)),
            "p05": float(np.quantile(values, 0.05)),
            "p95": float(np.quantile(values, 0.95)),
            "trend_slope_per_day": float(slope),
            "relative_slope_per_day": relative_slope,
            "r2": r2,
            "confident": confident,
            "raw_direction": raw_direction,
            "volatility_ratio": residual_ratio,
            "volatility_flag": volatility_flag,
            "configured_direction_preference": configured_preference,
            "direction_preference": preference,
            "direction_preference_source": preference_source,
            "fr404_applicable": fr404_applicable,
            "fr404_nearest_edge": fr404_nearest_edge,
            "fr404_edge_distance": fr404_edge_distance,
            "fr404_inferred_direction": fr404_direction,
            "fr404_inference_confidence": fr404_confidence,
            # Giữ alias cũ để tương thích với consumer đã có.
            "percent_direction_confidence": fr404_confidence,
            "trend_label": label,
        }
        components = pd.DataFrame(
            {
                "timestamp": index,
                "ne_id": ne_id,
                "cell_id": cell_id,
                "kpi_name": kpi_name,
                "value": values,
                "trend": trend,
                "seasonal": seasonal,
                "residual": residual,
                "was_imputed": imputed.to_numpy(dtype=bool),
            }
        )
        return summary, components
