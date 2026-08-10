# Báo cáo thay đổi — lọc dữ liệu MinIO theo danh sách trạm

## Mục tiêu thực hiện

- Không tạo database KPI cục bộ trong RKAA.
- KPI/counter vẫn đọc trực tiếp từ Parquet trên MinIO qua DuckDB adapter.
- Không ghi, sửa hoặc xóa dữ liệu trên MinIO.
- Thêm phương thức lấy dữ liệu chỉ cho danh sách trạm mong muốn.
- Giữ nguyên luồng cũ đọc toàn bộ hoặc lọc chính xác một `cellname`.

## Luồng sau khi sửa

```text
station list (CLI hoặc YAML)
        ↓
MinioCollectionService.collect_for_stations()
        ↓
MinioKPIAdapter.fetch_kpi_wide_dataframe_for_stations()
        ↓
build_minio_kpi_query(station_ids=...)
        ↓
SELECT ... FROM read_parquet(...)
WHERE time AND station/cellname prefix filter
        ↓
wide DataFrame
        ↓
MinioKPINormalizer
        ↓
long DataFrame / CSV
```

## File sửa

### `src/rkaa/domain/data_collector/minio_query_builder.py`
- Thêm tham số `station_ids`.
- Thêm `_build_station_filter()`.
- Với station `gHM00001`, query khớp `cellname = 'gHM00001'` hoặc prefix `gHM00001_`.
- Dùng placeholder `?`; giá trị station không ghép trực tiếp vào SQL.
- Giữ filter `cellname` cũ.
- Không cho dùng `cellname` và `station_ids` cùng lúc để tránh filter mơ hồ.
- Bổ sung kiểm tra kiểu cho `quote_identifier()` và `limit > 0`.

### `src/rkaa/domain/data_collector/minio_kpi_adapter.py`
- Giữ `fetch_kpi_wide_dataframe()` cũ.
- Thêm `fetch_kpi_wide_dataframe_for_stations()`.
- Danh sách rỗng trả DataFrame rỗng, không query MinIO.
- Gom phần execute SELECT vào `_execute_query()`.

### `src/rkaa/domain/data_collector/minio_collection_service.py`
- Giữ `collect_once()` cũ.
- Thêm `collect_for_stations()`.
- Chuẩn hóa station list rồi gọi adapter mới.
- Output vẫn qua normalizer wide → long như trước.

### `scripts/run_collection_once.py`
- Thêm `--station` (có thể lặp nhiều lần).
- Thêm `--stations-file` để đọc YAML.
- Nếu có station list thì gọi `collect_for_stations()`; nếu không thì luồng cũ không đổi.
- Không tạo hoặc đọc SQLite KPI.

### `README.md`
- Thêm cách lọc station trực tiếp và bằng YAML.

### `tests/unit/test_minio_query_builder.py`
- Giữ test filter cell cũ.
- Thêm test TypeError cho identifier sai kiểu.
- Thêm test nhiều station và params.
- Thêm test không cho trộn exact cell và station list.

## File thêm mới

### `src/rkaa/domain/data_collector/station_selection.py`
- Chuẩn hóa danh sách station: trim, bỏ rỗng, bỏ trùng.
- Không phụ thuộc MinIO, DuckDB hoặc YAML.

### `src/rkaa/infrastructure/config/station_list_loader.py`
- Đọc `stations:` từ file YAML.
- Chỉ là nguồn cung cấp list, không lưu dữ liệu KPI.

### `src/rkaa/infrastructure/config/__init__.py`
- Khai báo package config infrastructure.

### `configs/stations.example.yaml`
- Mẫu danh sách station cho người vận hành chỉnh sửa.

### `tests/unit/test_station_selection.py`
- Test chuẩn hóa và validate station list.

### `tests/unit/test_station_list_loader.py`
- Test đọc station list từ YAML.

### `tests/unit/test_minio_collection_service_station_filter.py`
- Test service truyền đúng station list xuống adapter và vẫn normalize 7 KPI.

## Không thay đổi

- Không tạo SQLite để chứa KPI.
- Không sửa `minio_duckdb.py`.
- Không sửa `minio_kpi_normalizer.py`.
- Không thay đổi 7 KPI hiện tại.
- Không thực hiện `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER` hay thao tác ghi object lên MinIO.
- SQLite của FR-103, nếu dùng, chỉ tiếp tục chứa Impact Event như trước.
