# RKAA — FR-101, FR-103 và lọc danh sách trạm

Dự án hiện đọc KPI/counter chính thức từ MinIO cho FR-101 và quản lý Impact Event nhập thủ công cho FR-103. SQLite chỉ lưu metadata Impact Event, không sao chép dữ liệu KPI từ MinIO.

## Cài đặt

Yêu cầu Python 3.11 trở lên.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install -e ".[dev]"
```

Trên Windows PowerShell, kích hoạt môi trường bằng:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Cấu hình

FR-101 dùng file secret cục bộ `secrets/minio.local` (có mẫu `secrets/minio.local.example`). Danh sách 8 KPI và các counter cần thu thập được khai báo trong `configs/kpi_mapping.yaml`; `canonical_name` luôn bằng `source_column`, và counter được đánh dấu bằng `is_counter=true`. FR-103 tiếp tục dùng `configs/impact_types.yaml`.

## Chạy FR-101

Kiểm tra kết nối và xem cấu trúc dữ liệu:

```bash
python scripts/minio_probe.py --limit 5
```

Thu thập một khoảng dữ liệu:

```bash
python scripts/run_collection_once.py \
  --start-time "2026-07-01 00:00:00" \
  --end-time "2026-07-02 00:00:00" \
  --limit 100
```

### Lọc dữ liệu theo danh sách trạm

Không có database KPI cục bộ. Dữ liệu KPI vẫn được đọc trực tiếp từ Parquet trên MinIO. Danh sách trạm chỉ được dùng để bổ sung điều kiện `WHERE` cho câu `SELECT`.

Lọc bằng tham số lặp lại:

```bash
python scripts/run_collection_once.py \
  --start-time "2026-07-01 00:00:00" \
  --end-time "2026-07-02 00:00:00" \
  --station gHM00001 \
  --station gHM00072
```

Hoặc copy `configs/stations.example.yaml` thành `configs/stations.yaml`, sửa danh sách rồi chạy:

```bash
python scripts/run_collection_once.py \
  --start-time "2026-07-01 00:00:00" \
  --end-time "2026-07-02 00:00:00" \
  --stations-file configs/stations.yaml
```

Danh sách station được lọc trực tiếp theo cột `ne` của Parquet. Cột `cellname` được giữ riêng thành `cell_id`; luồng `--cellname` vẫn lọc chính xác một cell.

## Chạy FR-103

Xem toàn bộ lệnh và tham số:

```bash
python scripts/manage_impact.py --help
python scripts/manage_impact.py create --help
```

Tạo một Impact Event:

```bash
python scripts/manage_impact.py create \
  --ne gHM00001 \
  --t1 "2026-07-15 16:50:00" \
  --t2 ongoing \
  --type SOFTWARE_UPGRADE \
  --description "Nâng cấp phần mềm gNB" \
  --operator engineer_a
```

Liệt kê dữ liệu đã lưu:

```bash
python scripts/manage_impact.py list
```

Các thao tác `show`, `update`, `close` và `delete` được mô tả trực tiếp trong phần trợ giúp của script.

## Kiểm thử

```bash
python -m compileall -q src scripts
python -m pytest -q
python -m ruff check src scripts tests
```

Dữ liệu tạm mặc định được ghi trong thư mục `tmp/`.

Schema long-format sau FR-101 giữ riêng định danh NE và cell:

```text
timestamp, period_end, ne_id, cell_id, kpi_name, value, unit, quality_flag, is_counter
```

Với dữ liệu long-format, một giá trị KPI được định danh bởi
`timestamp + period_end + ne_id + cell_id + kpi_name`.

## Chạy FR-201 — Lọc nhiễu dữ liệu

FR-201 chạy trên nhánh KPI sau FR-203, không ghi hoặc sửa dữ liệu trên MinIO.
Cấu hình mặc định nằm tại `configs/data_cleaning.yaml`. Counter không qua FR-201 trong Pha 3.

Thứ tự lọc:

1. Null/sentinel.
2. Impact window lấy từ metadata FR-103 nếu database tồn tại.
3. Counter reset / NE restart (mặc định OFF cho tới khi cấu hình cumulative counter phù hợp).
4. Statistical outlier: IQR mặc định ON; Z-score đã cài sẵn nhưng mặc định OFF.
5. Custom rule theo từng KPI.

Chạy với output mặc định:

```bash
python scripts/run_cleaning_once.py
```

Mặc định script đọc snapshot observation KPI từ FR-203 và ghi hai file:

```text
tmp/phase3/baseline_ready_kpi.csv
tmp/phase3/baseline_excluded_kpi.csv
```

`baseline_ready_kpi.csv` là nhánh dữ liệu sạch dùng để xây baseline.
`observation_metrics.csv` từ FR-203 vẫn được giữ riêng và chứa cả KPI + counter, nên statistical outlier bị loại khỏi
baseline không bị mất khỏi luồng quan sát bất thường.

Có thể chỉ định file khác:

```bash
python scripts/run_cleaning_once.py \
  --input tmp/phase3/observation_metrics.csv \
  --config configs/data_cleaning.yaml \
  --cleaned-output tmp/phase3/baseline_ready_kpi.csv \
  --excluded-output tmp/phase3/baseline_excluded_kpi.csv
```

Bật/tắt từng bước lọc bằng `enabled: true/false` trong YAML. Nếu một nhóm
`ne_id + cell_id + kpi_name` không đủ `min_samples`, IQR/Z-score tự bỏ qua nhóm đó và
không chuyển dữ liệu sang `excluded_kpi.csv`.

## FR-202 — Maintenance Window / Special Event

FR-202 dùng chung SQLite metadata `tmp/rkaa_metadata.db` với FR-103; SQLite chỉ lưu
metadata event, không lưu KPI. Hai trường mới là `event_category` và
`exclude_from_baseline`. Database FR-103 cũ được migrate tự động, không mất event.

Tạo maintenance window (mặc định loại khỏi baseline):

```bash
python scripts/manage_impact.py create \
  --ne gHM00001 \
  --t1 "2026-08-10 01:00:00" \
  --t2 "2026-08-10 03:00:00" \
  --type SOFTWARE_UPGRADE \
  --category MAINTENANCE \
  --description "Planned maintenance" \
  --operator engineer_a
```

`SPECIAL_EVENT` cũng mặc định `exclude_from_baseline=True`. Với `IMPACT`, nếu không
chỉ định policy thì giữ chế độ legacy để FR-201 quyết định theo
`filters.impact_window.excluded_impact_types`. Có thể override bằng
`--exclude-from-baseline` hoặc `--include-in-baseline`.

FR-201 gọi `EventCalendarService`, chỉ chuyển event được phép exclude thành
`ExclusionWindow`; dữ liệu KPI gốc và metadata event vẫn được giữ.

## FR-203 — Data Quality Check

Chạy sau FR-101:

```bash
python scripts/run_data_quality_once.py
```

Mặc định đọc `tmp/minio_kpi_long.csv`, dùng `configs/data_quality.yaml`, và sinh:

```text
tmp/fr203/quality_checked_metrics.csv
tmp/phase3/observation_metrics.csv
tmp/fr203/data_quality_issues.csv
tmp/fr203/data_quality_summary.csv
```

FR-203 chạy chung cho KPI và counter: chuẩn hóa timestamp/value/schema,
exact/conflicting duplicate, gap theo `ne_id + cell_id + kpi_name` và range validation.
KPI tiếp tục có local spike bằng rolling median + MAD; counter Pha 3 chỉ áp kiểm tra cơ bản
`value >= 0` và không chạy local-spike/IQR/Z-score. Exact duplicate giữ một bản;
conflicting duplicate và local spike chỉ được gắn cờ, không tự xóa.

Range validation KPI dùng lại rule từ `configs/data_cleaning.yaml`; counter dùng policy
chung `counter_min_value: 0` trong `configs/data_quality.yaml`.

Luồng Pha 3 mặc định:

```text
MinIO snapshot -> FR-203 -> observation_metrics.csv (KPI + Counter + quality flags)
                                  |
                                  |-- KPI -----> FR-201 -> baseline_ready_kpi.csv -> FR-401/402
                                  |
                                  +-- KPI + Counter ---------------------------> Pha phân tích sau
```

FR-401/FR-402 còn gắn `clean_day_count` và `baseline_reliable` theo BR-01; mặc định
baseline chỉ được coi là đáng tin khi có ít nhất 14 ngày dữ liệu sạch.

## Long-history snapshot cho dữ liệu 5 phút

Granularity vận hành hiện tại là **5 phút**. `period_end` được tính bằng
`timestamp + 5 phút`; FR-203 cũng dùng `expected_interval_minutes: 5`.
Local-spike rolling window mặc định giữ ý nghĩa 24 giờ nên dùng 288 mẫu, với
minimum history 72 mẫu (6 giờ).

Để lấy lịch sử dài mà không giữ toàn bộ dữ liệu trong RAM, dùng script chunked:

```bash
python scripts/run_history_collection.py \
  --start-time "2026-05-01 00:00:00" \
  --end-time "2026-08-01 00:00:00" \
  --chunk-hours 6 \
  --metric-kind kpi
```

Script chỉ SELECT MinIO, đọc danh sách NE từ `configs/stations.yaml`, và lưu mỗi
chunk thành Parquet ZSTD trong `tmp/history_metrics/`. Mặc định chỉ lấy KPI để
phục vụ quan sát dài hạn/trend; có thể dùng `--metric-kind all` hoặc
`--metric-kind counter`, hoặc `--metric "<tên metric>"` để giới hạn phạm vi.
Không có row limit mặc định; `--limit-per-chunk` chỉ dành cho smoke test.

Query một phần dữ liệu đã lưu mà không load toàn bộ dataset:

```bash
python scripts/query_saved_metrics.py \
  --store tmp/history_metrics \
  --ne gHM00001 \
  --cell CELL_A \
  --metric "ENDC SSR VTNET IniAtt (%)" \
  --start-time "2026-07-01 00:00:00" \
  --end-time "2026-07-02 00:00:00" \
  --limit 200 \
  --output tmp/history_subset.csv
```

`Matched rows` là tổng số record thỏa filter; `--limit` chỉ giới hạn số dòng
hiển thị/xuất. Nếu cần observation có cờ FR-203, đưa subset vừa query qua:

```bash
python scripts/run_data_quality_once.py \
  --input tmp/history_subset.csv \
  --observation-output tmp/history_subset_observation.csv
```

MinIO vẫn là raw source of truth; local Parquet chỉ là snapshot analytical để
tránh query lại cùng một lịch sử dài và không thay thế SQLite metadata.
