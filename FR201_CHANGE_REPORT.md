# Báo cáo triển khai FR-201

## Phạm vi

FR-201 được triển khai như một lớp làm sạch chạy sau dữ liệu long-format của FR-101.
Không có thao tác ghi, sửa hoặc xóa dữ liệu Parquet trên MinIO. Hai output mặc định:

- `tmp/fr201/cleaned_kpi.csv`: record còn được dùng cho phân tích tiếp.
- `tmp/fr201/excluded_kpi.csv`: record bị loại cùng `filter_stage`, `filter_reason`, `detail`.

## File hiện có đã sửa

### `src/rkaa/domain/data_collector/minio_kpi_normalizer.py`

Trước đây null KPI bị bỏ qua ngay ở FR-101. Đã đổi để giữ record null với:

- `value = NaN`
- `quality_flag = MISSING`

Mục đích: FR-201 có thể nhìn thấy, thống kê và loại null có lý do thay vì mất record trước khi tới bộ lọc.
Không thay đổi câu query MinIO và không thay đổi dữ liệu nguồn.

### `tests/unit/test_minio_kpi_normalizer.py`

Thêm test xác nhận null được giữ lại cho FR-201.

### `README.md`

Thêm hướng dẫn chạy FR-201, hai CSV output, bật/tắt filter và hành vi khi thiếu mẫu.

## File mới

### Cấu hình

- `configs/data_cleaning.yaml`
  - Null/sentinel: ON.
  - Impact window: ON.
  - Restart: OFF mặc định.
  - IQR: ON mặc định.
  - Z-score: OFF mặc định.
  - Custom rule: ON.

### Domain `src/rkaa/domain/noise_filter/`

- `models.py`: dataclass cấu hình, `ExclusionWindow`, `FilterOutcome`, `CleanResult`.
- `rule.py`: Protocol chung cho filter.
- `utils.py`: validate cột, parse timestamp, tách cleaned/excluded.
- `null_sentinel_filter.py`: null, non-numeric, +/-inf, sentinel.
- `impact_window_filter.py`: loại `[t1, t2)` theo NE; hỗ trợ exact hoặc station-prefix.
- `restart_filter.py`: phát hiện cumulative-counter reset, xác nhận tăng trở lại, tương quan nhiều counter để suy ra NE restart, rồi loại restart + grace window.
- `statistical_outlier_filter.py`: IQR và Z-score theo từng `ne_id + kpi_name`; tự skip nhóm không đủ mẫu; Z-score skip khi std=0; IQR skip khi IQR=0.
- `custom_rule_filter.py`: range rule theo KPI.
- `service.py`: orchestration đúng thứ tự FR-201.

### Infrastructure

- `src/rkaa/infrastructure/config/data_cleaning_loader.py`: đọc/validate YAML thành cấu hình domain.

### Script

- `scripts/run_cleaning_once.py`: đọc CSV long-format, tùy chọn đọc Impact Event từ `tmp/rkaa_metadata.db`, chạy FR-201 và sinh hai CSV.

Script không tạo database Impact Event mới nếu DB chưa tồn tại; khi không có DB/window thì bước impact được bỏ qua và chương trình vẫn chạy.

### Test mới

- `tests/unit/noise_filter/test_null_sentinel_filter.py`
- `tests/unit/noise_filter/test_impact_window_filter.py`
- `tests/unit/noise_filter/test_restart_filter.py`
- `tests/unit/noise_filter/test_statistical_outlier_filter.py`
- `tests/unit/noise_filter/test_custom_rule_filter.py`
- `tests/unit/noise_filter/test_noise_filter_service.py`
- `tests/unit/test_data_cleaning_loader.py`
- `tests/integration/test_noise_filter_pipeline.py`

## Chi tiết thuật toán

### 1. Null / sentinel

Loại `None/NaN`, giá trị không phải số, `+/-inf` và sentinel được khai báo trong YAML.
Sentinel mặc định để rỗng vì phải lấy từ quy ước EMS thật, không tự đoán.

### 2. Impact window

Đọc Impact Event FR-103 nếu metadata DB tồn tại. Record khớp NE và nằm trong `[t1, t2)` bị loại. Với event ongoing (`t2=None`), tất cả record từ `t1` trở đi trong input hiện tại bị loại.

### 3. Restart detector

Mã nguồn có đầy đủ nhưng `enabled: false` mặc định vì 7 KPI hiện tại không phải cumulative counter.
Khi bật, detector chỉ xét `eligible_metrics` cấu hình và kiểm tra:

1. Previous value >= `min_previous_value`.
2. Current value >= 0 và <= `reset_max_value`.
3. Mức giảm >= `min_drop_ratio`.
4. Có `confirmation_points` điểm tiếp theo không giảm và cuối cùng tăng cao hơn giá trị reset.
5. Có ít nhất `min_concurrent_counters` counter reset trong `concurrent_window_minutes` để suy ra NE restart.
6. Loại record từ thời điểm restart tới hết `post_restart_grace_minutes`.

### 4. IQR / Z-score

Cả hai tính riêng từng nhóm `ne_id + kpi_name`.

- IQR ON mặc định, `multiplier=1.5`, `min_samples=24`.
- Z-score OFF mặc định, `threshold=3.0`, `min_samples=100`.
- Nếu thiếu mẫu: skip riêng nhóm, dữ liệu vẫn nằm trong cleaned output.
- IQR=0 hoặc std=0: skip riêng nhóm.
- Nếu sau này bật đồng thời IQR + Z-score, `combination: any` nghĩa một trong hai đánh dấu là đủ để exclude; `all` yêu cầu cả hai.

Z-score chỉ dùng để phát hiện outlier; không thay cột `value` bằng giá trị chuẩn hóa.

### 5. Custom rule

Mặc định đặt domain hợp lệ:

- 5 KPI phần trăm: 0..100.
- Max RRC Connected: >=0.
- NSA PS Traffic: >=0.

Không đặt upper bound cho user/traffic.

## Kiểm thử

Đã chạy:

```text
python -m compileall -q src scripts
python -m pytest -q
47 passed
```

Smoke test CLI cũng đã sinh đúng hai CSV và terminal summary.

`ruff` chưa chạy trong runtime đóng gói do môi trường hiện tại không cài module `ruff`; dependency dev vẫn còn trong `pyproject.toml`.

## Giới hạn chưa được claim

Các unit/integration test hiện dùng dữ liệu synthetic. Chưa có labeled dataset thực tế để chứng minh các tiêu chí định lượng của SRS như counter-reset accuracy >=98% hoặc outlier false-positive <=1%. Các chỉ tiêu đó cần benchmark/gold label riêng trước khi khẳng định đạt acceptance criteria.
