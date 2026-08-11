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

FR-101 dùng file secret cục bộ `secrets/minio.local` (có mẫu `secrets/minio.local.example`). Bản MinIO này giữ mapping 7 KPI trực tiếp trong `DEFAULT_KPI_MAPPING` của `minio_kpi_normalizer.py` để khớp mã nguồn cũ. FR-103 tiếp tục dùng `configs/impact_types.yaml`.

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
timestamp, period_end, ne_id, cell_id, kpi_name, value, unit, quality_flag
```

Với dữ liệu long-format, một giá trị KPI được định danh bởi
`timestamp + period_end + ne_id + cell_id + kpi_name`.

## Chạy FR-201 — Lọc nhiễu dữ liệu

FR-201 chạy sau FR-101 trên file long-format, không ghi hoặc sửa dữ liệu trên MinIO.
Cấu hình mặc định nằm tại `configs/data_cleaning.yaml`.

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

Mặc định script đọc `tmp/minio_kpi_long.csv` và ghi hai file:

```text
tmp/fr201/cleaned_kpi.csv
tmp/fr201/excluded_kpi.csv
```

`cleaned_kpi.csv` là dữ liệu còn được dùng cho phân tích tiếp. `excluded_kpi.csv`
giữ lại record đã bị loại và thêm `filter_stage`, `filter_reason`, `detail` để audit.

Có thể chỉ định file khác:

```bash
python scripts/run_cleaning_once.py \
  --input tmp/minio_kpi_long.csv \
  --config configs/data_cleaning.yaml \
  --cleaned-output tmp/fr201/cleaned_kpi.csv \
  --excluded-output tmp/fr201/excluded_kpi.csv
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
tmp/fr203/quality_checked_kpi.csv
tmp/fr203/data_quality_issues.csv
tmp/fr203/data_quality_summary.csv
```

FR-203 thực hiện: chuẩn hóa timestamp/value/schema, exact/conflicting duplicate,
gap theo `ne_id + cell_id + kpi_name`, range validation, và local spike bằng rolling median
+ MAD. Exact duplicate giữ một bản; conflicting duplicate và local spike chỉ được
gắn cờ, không tự xóa. Gap > 2 giờ được in cảnh báo trên terminal.

Range validation dùng lại rule từ `configs/data_cleaning.yaml` để không duy trì hai
bộ giới hạn KPI khác nhau.

Để chạy FR-201 trên output đã quality-check:

```bash
python scripts/run_cleaning_once.py --input tmp/fr203/quality_checked_kpi.csv
```
