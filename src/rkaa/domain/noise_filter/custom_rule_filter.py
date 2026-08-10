"""Bước 5 FR-201: lọc dữ liệu theo rule nghiệp vụ cấu hình riêng cho từng KPI.

Ví dụ rule:
- KPI phần trăm hợp lệ trong khoảng 0..100.
- KPI lưu lượng hoặc số user chỉ yêu cầu giá trị >= 0.

Filter này không tự suy luận ngưỡng. Nó chỉ áp dụng các min/max đã được cấu hình
trong ``CustomRuleConfig``. Record vi phạm rule sẽ được chuyển sang
``excluded_df`` cùng lý do; record còn lại đi vào ``cleaned_df``.
"""

from __future__ import annotations

import pandas as pd

from rkaa.domain.noise_filter.models import CustomRuleConfig, FilterOutcome
from rkaa.domain.noise_filter.utils import require_columns, split_by_mask


class CustomRuleFilter:
    """Áp dụng các giới hạn nghiệp vụ min/max cho từng KPI."""

    def __init__(self, config: CustomRuleConfig) -> None:
        # config.rules chứa mapping:
        # kpi_name -> rule(min_value, max_value)
        self.config = config

    def apply(self, df: pd.DataFrame) -> FilterOutcome:
        """Lọc các record vi phạm rule và trả về dữ liệu giữ lại/bị loại."""

        # Filter cần biết tên KPI để chọn đúng rule và cần cột value để so ngưỡng.
        require_columns(df, ("kpi_name", "value"))

        # Chuyển value sang dạng số để có thể so sánh min/max.
        # Giá trị không chuyển được thành số trở thành NaN; trường hợp đó đã được
        # xử lý ở bước Null/Sentinel trước khi tới CustomRuleFilter.
        numeric = pd.to_numeric(df["value"], errors="coerce")

        # mask=True nghĩa là record đã vi phạm ít nhất một custom rule và sẽ bị loại.
        mask = pd.Series(False, index=df.index)

        # reasons/details dùng để giải thích trong excluded_kpi.csv:
        # - reasons: mã lý do ngắn gọn như BELOW_MIN, ABOVE_MAX.
        # - details: ngưỡng cụ thể đã bị vi phạm.
        reasons = pd.Series("", index=df.index, dtype="object")
        details = pd.Series("", index=df.index, dtype="object")

        # Đếm số rule có KPI tương ứng thực sự xuất hiện trong DataFrame hiện tại.
        applied_rules = 0

        for kpi_name, rule in self.config.rules.items():
            # kpi_mask=True tại các dòng thuộc đúng KPI đang xét.
            kpi_mask = df["kpi_name"] == kpi_name
            if not kpi_mask.any():
                # KPI không có trong batch hiện tại thì không cần áp rule.
                continue

            applied_rules += 1

            if rule.min_value is not None:
                # below=True khi đúng KPI và value nhỏ hơn ngưỡng tối thiểu.
                below = kpi_mask & (numeric < rule.min_value)

                # Chỉ ghi reason/detail cho record chưa bị rule trước đánh dấu.
                # Điều này tránh ghi đè lý do đầu tiên nếu một record vô tình
                # thỏa nhiều điều kiện loại.
                new_rows = below & ~mask
                reasons.loc[new_rows] = "BELOW_MIN"
                details.loc[new_rows] = "valid_min=" + str(rule.min_value)

                # Gộp các dòng vi phạm min vào mask tổng bằng OR logic.
                mask |= below

            if rule.max_value is not None:
                # above=True khi đúng KPI và value lớn hơn ngưỡng tối đa.
                above = kpi_mask & (numeric > rule.max_value)

                # Tương tự min: chỉ ghi lý do cho record chưa bị đánh dấu trước đó.
                new_rows = above & ~mask
                reasons.loc[new_rows] = "ABOVE_MAX"
                details.loc[new_rows] = "valid_max=" + str(rule.max_value)

                # Gộp các dòng vi phạm max vào mask tổng.
                mask |= above

        # split_by_mask chia DataFrame thành hai phần:
        # - mask=False -> cleaned_df: dữ liệu được giữ lại.
        # - mask=True  -> excluded_df: dữ liệu bị loại và được bổ sung
        #   filter_stage/filter_reason/detail để audit.
        cleaned, excluded = split_by_mask(
            df,
            mask,
            stage="CUSTOM_RULE",
            reasons=reasons,
            details=details,
        )

        # summary phục vụ log cuối lần chạy FR-201.
        return FilterOutcome(
            cleaned_df=cleaned,
            excluded_df=excluded,
            summary={
                "status": "ENABLED",
                "excluded": int(mask.sum()),
                "rules_applied": applied_rules,
            },
        )
