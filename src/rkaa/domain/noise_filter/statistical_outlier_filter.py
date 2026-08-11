"""Bước 4 FR-201: phát hiện outlier bằng IQR và/hoặc Z-score.

File này chỉ xử lý *statistical outlier* trên dữ liệu KPI dạng long-format.
Mỗi nhóm dữ liệu được xét độc lập theo cặp ``ne_id + cell_id + kpi_name`` để tránh
trộn các trạm hoặc KPI có phân phối/thang đo khác nhau.

Hai phương pháp được hỗ trợ:
- IQR (Interquartile Range): mặc định phù hợp cho dữ liệu chưa chắc phân phối chuẩn.
- Z-score: có thể bật riêng khi dữ liệu đủ lớn và ổn định hơn.

Kết quả trả về ``FilterOutcome`` gồm:
- ``cleaned_df``: các dòng được giữ lại sau bước lọc này.
- ``excluded_df``: các dòng bị đánh dấu outlier, kèm lý do và chi tiết ngưỡng.
- ``summary``: thống kê số group đã xử lý / bị skip / số dòng bị loại.

Lưu ý: filter chỉ thao tác trên DataFrame trong bộ nhớ, không sửa dữ liệu MinIO.
"""

from __future__ import annotations

import pandas as pd

from rkaa.domain.noise_filter.models import FilterOutcome, StatisticalOutlierConfig
from rkaa.domain.noise_filter.utils import require_columns, split_by_mask


class StatisticalOutlierFilter:
    """Phát hiện outlier thống kê theo từng ``ne_id + cell_id + kpi_name``.

    ``config`` quyết định:
    - IQR có bật hay không, multiplier và số mẫu tối thiểu.
    - Z-score có bật hay không, threshold và số mẫu tối thiểu.
    - Nếu bật đồng thời cả hai thì dùng cách kết hợp ``any`` hoặc ``all``.
    """

    def __init__(self, config: StatisticalOutlierConfig) -> None:
        self.config = config

    def apply(self, df: pd.DataFrame) -> FilterOutcome:
        """Chạy lọc outlier và trả dữ liệu giữ lại + dữ liệu bị loại.

        Yêu cầu đầu vào có tối thiểu 3 cột:
        - ``ne_id``: định danh NE/trạm.
        - ``cell_id``: định danh cell trong NE.
        - ``kpi_name``: tên KPI.
        - ``value``: giá trị KPI cần kiểm tra.

        Mỗi nhóm ``ne_id + cell_id + kpi_name`` được tính IQR/Z-score riêng.
        Nếu số mẫu của một nhóm nhỏ hơn ``min_samples`` thì phương pháp tương ứng
        tự động SKIP cho riêng nhóm đó; dữ liệu của nhóm vẫn được giữ lại.
        """

        # Đảm bảo input có đủ cột bắt buộc trước khi tính toán.
        require_columns(df, ("ne_id", "cell_id", "kpi_name", "value"))

        # Nếu cả IQR và Z-score đều tắt thì không làm gì với dữ liệu.
        # Trả lại bản copy của df và một excluded_df rỗng để giữ cùng interface.
        if not self.config.iqr.enabled and not self.config.z_score.enabled:
            return FilterOutcome(
                cleaned_df=df.copy(),
                excluded_df=pd.DataFrame(
                    columns=[*df.columns.tolist(), "filter_stage", "filter_reason", "detail"]
                ),
                summary={"status": "DISABLED_METHODS", "excluded": 0},
            )

        # Chuyển cột value sang số để tính thống kê.
        # Giá trị không chuyển được thành số sẽ thành NaN và bị bỏ qua ở bước tính
        # thống kê. Việc loại null/non-numeric đã thuộc NullSentinelFilter trước đó.
        numeric = pd.to_numeric(df["value"], errors="coerce")

        # Mask Boolean có cùng index với df.
        # True = dòng đó bị phương pháp tương ứng đánh dấu là outlier.
        iqr_mask = pd.Series(False, index=df.index)
        z_mask = pd.Series(False, index=df.index)

        # Lưu mô tả chi tiết cho từng dòng bị phát hiện để ghi vào excluded CSV,
        # ví dụ lower/upper của IQR hoặc z/mean/std của Z-score.
        iqr_detail = pd.Series("", index=df.index, dtype="object")
        z_detail = pd.Series("", index=df.index, dtype="object")

        # summary dùng để log/đánh giá trạng thái của từng phương pháp.
        # "group" ở đây nghĩa là một chuỗi thời gian ne_id + cell_id + kpi_name.
        summary = {
            "status": "ENABLED",
            "iqr_groups_processed": 0,
            "iqr_groups_skipped_insufficient": 0,
            "iqr_groups_skipped_zero_iqr": 0,
            "z_groups_processed": 0,
            "z_groups_skipped_insufficient": 0,
            "z_groups_skipped_zero_std": 0,
        }

        # Tạo cột tạm _value rồi group theo đúng chuỗi thời gian NE + Cell + KPI.
        # Hai cell khác nhau của cùng NE không được trộn chung baseline thống kê.
        grouped = df.assign(_value=numeric).groupby(
            ["ne_id", "cell_id", "kpi_name"],
            sort=False,
        )

        for (_, _, _), group in grouped:
            # Bỏ NaN trước khi tính thống kê.
            values = group["_value"].dropna()
            sample_count = len(values)

            # -------------------- IQR --------------------
            if self.config.iqr.enabled:
                # Không đủ số mẫu tối thiểu -> tự động skip IQR cho group này.
                # Các dòng vẫn được giữ, không đưa vào excluded_df chỉ vì thiếu mẫu.
                if sample_count < self.config.iqr.min_samples:
                    summary["iqr_groups_skipped_insufficient"] += 1
                else:
                    # Q1 = phân vị 25%, Q3 = phân vị 75%.
                    # IQR = khoảng giữa Q3 và Q1.
                    q1 = float(values.quantile(0.25))
                    q3 = float(values.quantile(0.75))
                    iqr = q3 - q1

                    # Nếu mọi giá trị tập trung đến mức IQR = 0 thì không có
                    # khoảng biến thiên để áp ngưỡng theo IQR. Với cấu hình "skip"
                    # sẽ bỏ qua phương pháp này cho group đó.
                    if iqr == 0 and self.config.iqr.zero_iqr == "skip":
                        summary["iqr_groups_skipped_zero_iqr"] += 1
                    else:
                        # Ngưỡng IQR chuẩn:
                        # lower = Q1 - multiplier * IQR
                        # upper = Q3 + multiplier * IQR
                        lower = q1 - self.config.iqr.multiplier * iqr
                        upper = q3 + self.config.iqr.multiplier * iqr

                        # True nếu value nằm ngoài [lower, upper].
                        current_mask = (values < lower) | (values > upper)
                        selected = current_mask[current_mask].index
                        iqr_mask.loc[selected] = True

                        # Ghi đủ thông tin để sau này nhìn excluded_kpi.csv có thể
                        # biết vì sao dòng bị IQR đánh dấu.
                        iqr_detail.loc[selected] = values.loc[selected].map(
                            lambda value: (
                                f"value={float(value):g}; lower={lower:g}; upper={upper:g}; "
                                f"q1={q1:g}; q3={q3:g}; multiplier={self.config.iqr.multiplier:g}"
                            )
                        )
                        summary["iqr_groups_processed"] += 1

            # -------------------- Z-SCORE --------------------
            if self.config.z_score.enabled:
                # Không đủ mẫu -> skip Z-score cho riêng group này.
                if sample_count < self.config.z_score.min_samples:
                    summary["z_groups_skipped_insufficient"] += 1
                else:
                    # mean: trung bình của group.
                    # std: độ lệch chuẩn population (ddof=0).
                    mean = float(values.mean())
                    std = float(values.std(ddof=0))

                    # std = 0 nghĩa là tất cả giá trị bằng nhau, không thể tính
                    # z = (x - mean) / std. Với zero_std="skip" thì bỏ qua group.
                    if std == 0 and self.config.z_score.zero_std == "skip":
                        summary["z_groups_skipped_zero_std"] += 1
                    else:
                        # Chuẩn hóa từng value thành Z-score.
                        # Không thay đổi cột value gốc; z_values chỉ dùng để detect.
                        z_values = (values - mean) / std

                        # Một điểm được coi là Z-score outlier khi độ lớn tuyệt đối
                        # của z vượt threshold, ví dụ |z| > 3.
                        current_mask = z_values.abs() > self.config.z_score.threshold
                        selected = current_mask[current_mask].index
                        z_mask.loc[selected] = True

                        # Lưu z, threshold, mean và std để giải thích kết quả.
                        z_detail.loc[selected] = z_values.loc[selected].map(
                            lambda z: (
                                f"z={float(z):g}; threshold={self.config.z_score.threshold:g}; "
                                f"mean={mean:g}; std={std:g}"
                            )
                        )
                        summary["z_groups_processed"] += 1

        # Nếu bật đồng thời IQR và Z-score thì cần quy tắc kết hợp:
        # - any: chỉ cần một trong hai đánh dấu -> outlier.
        # - all: phải được cả IQR và Z-score cùng đánh dấu -> outlier.
        if self.config.iqr.enabled and self.config.z_score.enabled:
            if self.config.combination == "any":
                mask = iqr_mask | z_mask
            elif self.config.combination == "all":
                mask = iqr_mask & z_mask
            else:
                raise ValueError(
                    f"statistical_outlier.combination không hỗ trợ: {self.config.combination}"
                )
        elif self.config.iqr.enabled:
            mask = iqr_mask
        else:
            mask = z_mask

        # reasons/detail dùng để ghi nguyên nhân vào excluded_df.
        reasons = pd.Series("", index=df.index, dtype="object")
        details = pd.Series("", index=df.index, dtype="object")

        # Phân biệt ba trường hợp để biết dòng bị phát hiện bởi phương pháp nào.
        only_iqr = mask & iqr_mask & ~z_mask
        only_z = mask & z_mask & ~iqr_mask
        both = mask & iqr_mask & z_mask

        reasons.loc[only_iqr] = "IQR_OUTLIER"
        details.loc[only_iqr] = iqr_detail.loc[only_iqr]

        reasons.loc[only_z] = "Z_SCORE_OUTLIER"
        details.loc[only_z] = z_detail.loc[only_z]

        reasons.loc[both] = "IQR_AND_Z_SCORE_OUTLIER"
        details.loc[both] = (
            iqr_detail.loc[both].fillna("") + "; " + z_detail.loc[both].fillna("")
        )

        # split_by_mask:
        # - mask=False -> cleaned_df
        # - mask=True  -> excluded_df và thêm filter_stage/filter_reason/detail.
        cleaned, excluded = split_by_mask(
            df,
            mask,
            stage="STATISTICAL_OUTLIER",
            reasons=reasons,
            details=details,
        )

        # Tổng số record bị loại ở bước statistical outlier.
        summary["excluded"] = int(mask.sum())

        return FilterOutcome(cleaned_df=cleaned, excluded_df=excluded, summary=summary)
