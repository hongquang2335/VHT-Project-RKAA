"""Bước 1 FR-201: loại null, non-finite và sentinel."""

from __future__ import annotations

import math

import pandas as pd

from rkaa.domain.noise_filter.models import FilterOutcome, NullSentinelConfig
from rkaa.domain.noise_filter.utils import require_columns, split_by_mask


class NullSentinelFilter:
    def __init__(self, config: NullSentinelConfig) -> None:
        self.config = config

    def apply(self, df: pd.DataFrame) -> FilterOutcome:
        # FR-201 cần tối thiểu tên KPI và giá trị để kiểm tra dữ liệu lỗi.
        require_columns(df, ("kpi_name", "value"))

        # Giữ giá trị gốc để ghi chi tiết vào excluded_kpi.csv.
        # numeric là phiên bản ép kiểu số; giá trị không chuyển được sẽ thành NaN.
        original = df["value"]
        numeric = pd.to_numeric(original, errors="coerce")

        # null_mask: value thực sự là None/NaN/pd.NA.
        null_mask = original.isna()

        # non_numeric_mask: value có dữ liệu nhưng không thể chuyển thành số,
        # ví dụ "abc" hoặc một chuỗi không hợp lệ.
        non_numeric_mask = original.notna() & numeric.isna()

        # finite_mask xác định giá trị số hữu hạn.
        # NaN được tạm xem là True ở đây vì null đã được null_mask xử lý riêng.
        finite_mask = numeric.map(
            lambda value: True if pd.isna(value) else math.isfinite(float(value))
        )

        # non_finite_mask: các giá trị số như +inf hoặc -inf.
        non_finite_mask = numeric.notna() & ~finite_mask

        # sentinel_mask: đánh dấu các giá trị sentinel được khai báo trong config.
        # Ban đầu chưa có dòng nào là sentinel nên toàn bộ giá trị là False.
        sentinel_mask = pd.Series(False, index=df.index)

        # Sentinel dùng chung cho mọi KPI, ví dụ -999 nếu sau này EMS quy định như vậy.
        if self.config.global_values:
            sentinel_mask |= numeric.isin(self.config.global_values)

        # Sentinel riêng cho từng KPI.
        # Một giá trị chỉ bị đánh dấu khi vừa đúng KPI vừa thuộc danh sách sentinel của KPI đó.
        for kpi_name, sentinel_values in self.config.per_kpi.items():
            if not sentinel_values:
                continue
            sentinel_mask |= (df["kpi_name"] == kpi_name) & numeric.isin(sentinel_values)

        # mask cuối cùng: một dòng bị loại nếu thuộc ít nhất một nhóm lỗi bên dưới.
        mask = null_mask | non_numeric_mask | non_finite_mask | sentinel_mask

        # Hai Series này dùng để ghi nguyên nhân và chi tiết cho từng dòng bị loại.
        reasons = pd.Series("", index=df.index, dtype="object")
        details = pd.Series("", index=df.index, dtype="object")

        reasons.loc[null_mask] = "NULL"
        details.loc[null_mask] = "value is null/NaN"

        reasons.loc[non_numeric_mask] = "NON_NUMERIC"
        details.loc[non_numeric_mask] = original.loc[non_numeric_mask].map(
            lambda value: f"value={value!r}"
        )

        reasons.loc[non_finite_mask] = "NON_FINITE"
        details.loc[non_finite_mask] = original.loc[non_finite_mask].map(
            lambda value: f"value={value!r}"
        )

        # Chỉ gán lý do SENTINEL cho dòng thực sự bị loại vì sentinel,
        # không ghi đè lý do NULL / NON_NUMERIC / NON_FINITE đã xác định trước đó.
        # ~ nghĩa là NOT, & nghĩa là AND.
        sentinel_only = sentinel_mask & ~null_mask & ~non_numeric_mask & ~non_finite_mask
        reasons.loc[sentinel_only] = "SENTINEL"
        details.loc[sentinel_only] = original.loc[sentinel_only].map(
            lambda value: f"configured sentinel={value!r}"
        )

        # Tách DataFrame thành:
        # - cleaned: dữ liệu được giữ lại;
        # - excluded: dữ liệu bị loại, kèm filter_stage/filter_reason/detail.
        cleaned, excluded = split_by_mask(
            df,
            mask,
            stage="NULL_SENTINEL",
            reasons=reasons,
            details=details,
        )

        # Sau khi loại dữ liệu lỗi, chuẩn hóa cột value của cleaned thành kiểu số.
        if not cleaned.empty:
            cleaned["value"] = pd.to_numeric(cleaned["value"], errors="coerce")

        # Trả dữ liệu sạch, dữ liệu bị loại và thống kê số lượng theo từng nguyên nhân.
        return FilterOutcome(
            cleaned_df=cleaned,
            excluded_df=excluded,
            summary={
                "status": "ENABLED",
                "excluded": int(mask.sum()),
                "null": int(null_mask.sum()),
                "non_numeric": int(non_numeric_mask.sum()),
                "non_finite": int(non_finite_mask.sum()),
                "sentinel": int(sentinel_only.sum()),
            },
        )
