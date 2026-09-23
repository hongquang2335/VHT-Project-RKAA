# Bao Cao Ma Nguon Hien Tai RKAA

## 1. Tong quan hien trang

- Ten du an: `RKAA - RAN KPI Anomaly Analyzer`
- Kieu ung dung hien tai: `FastAPI backend`, chua co frontend rieng trong repo.
- Kieu dong goi: `src-layout` voi package chinh la `rkaa`.
- Database hien tai: `SQLite` theo cau hinh mac dinh `sqlite:///./rkaa.db`.
- Muc tieu nghiep vu da co trong ma nguon:
  - import du lieu KPI tu CSV
  - bao cao chat luong du lieu
  - tinh baseline KPI theo day period va week profile
  - quan ly impact event
  - phan tich tac dong truoc/sau impact event
- Nhung phan chua co trong source runtime hien tai:
  - anomaly detector phase 08 tro di chua implement
  - report HTML/PDF/Excel chua implement
  - frontend chua implement
  - auth, security, audit, trend, knowledge, alerting chua implement

## 2. Thu vien va cong nghe dang dung

### 2.1 Dependencies runtime

Khai bao trong [pyproject.toml](/C:/Users/quang/Desktop/thuc%20tap/RKAA/pyproject.toml:1):

- `fastapi`
  - dung de tao API va Swagger `/docs`
- `pydantic`
  - validate request/response
  - validate config va CSV input schema
- `sqlalchemy`
  - ORM model, session, repository, SQLite engine
- `uvicorn[standard]`
  - ASGI server de chay FastAPI

### 2.2 Dependencies dev

- `pytest`
  - unit test va integration test
- `httpx`
  - test client HTTP cho FastAPI
- `coverage`
  - do coverage
- `ruff`
  - lint va sap xep import

### 2.3 Thu vien Python standard library duoc dung nhieu

- `dataclasses`
- `datetime`
- `statistics`
- `math`
- `csv`
- `io`
- `pathlib`
- `logging`
- `json`
- `collections`
- `contextlib`
- `contextvars`
- `uuid`

## 3. Cay thu muc va vai tro tung khu vuc

```text
RKAA/
|-- configs/
|   `-- config.yaml
|-- docs/
|   |-- AGENT.md
|   |-- input_data_spec.md
|   |-- progress/
|   `-- codex/
|-- src/
|   `-- rkaa/
|       |-- main.py
|       |-- core/
|       |   |-- config.py
|       |   |-- exceptions.py
|       |   |-- error_handlers.py
|       |   `-- logging.py
|       |-- domain/
|       |   |-- data_collector/
|       |   |   |-- schemas.py
|       |   |   |-- csv_parser.py
|       |   |   `-- import_service.py
|       |   |-- noise_filter/
|       |   |   |-- null_filter.py
|       |   |   |-- range_validator.py
|       |   |   |-- duplicate_checker.py
|       |   |   |-- gap_detector.py
|       |   |   |-- counter_reset_detector.py
|       |   |   |-- iqr_outlier_filter.py
|       |   |   `-- data_quality_report.py
|       |   |-- maintenance_filter.py
|       |   |-- day_period_classifier.py
|       |   |-- week_profile_classifier.py
|       |   |-- baseline_grouping.py
|       |   |-- baseline_statistics.py
|       |   |-- baseline_confidence.py
|       |   |-- baseline_service.py
|       |   |-- impact_service.py
|       |   |-- window_resolver.py
|       |   |-- impact_data_loader.py
|       |   |-- delta_calculator.py
|       |   |-- welch_test.py
|       |   |-- mann_whitney_test.py
|       |   |-- impact_classifier.py
|       |   `-- impact_analysis_service.py
|       |-- infrastructure/
|       |   `-- data_store/
|       |       |-- base.py
|       |       |-- database.py
|       |       |-- models/
|       |       `-- repositories/
|       `-- presentation/
|           `-- api/
|               |-- kpi_import.py
|               |-- data_quality_report.py
|               |-- baseline.py
|               |-- impact.py
|               `-- impact_analysis.py
|-- tests/
|   |-- integration/
|   |-- unit/
|   |-- fixtures/
|   `-- conftest.py
|-- pyproject.toml
`-- uv.lock
```

### 3.1 `configs/`

- Chua cau hinh runtime.
- File [configs/config.yaml](/C:/Users/quang/Desktop/thuc%20tap/RKAA/configs/config.yaml:1) dang dinh nghia:
  - ten app
  - timezone
  - granularity KPI
  - so ngay clean toi thieu de baseline reliable
  - khung gio `busy`, `transition`, `off_peak`
  - database URL
  - log level

### 3.2 `src/rkaa/core/`

- Day la tang ha tang nen cho toan app:
  - `config.py`: nap config YAML va env override
  - `logging.py`: log JSON va correlation id
  - `exceptions.py`: dinh nghia `AppError`, `NotFoundError`
  - `error_handlers.py`: chuyen exception thanh JSON response thong nhat

### 3.3 `src/rkaa/infrastructure/data_store/`

- Day la tang persistence.
- `base.py`: declarative base cho SQLAlchemy
- `database.py`: tao engine, session factory, `session_scope()`
- `models/`: khai bao bang du lieu
- `repositories/`: thao tac CRUD va query theo use case

### 3.4 `src/rkaa/domain/`

- Day la tang nghiep vu chinh.
- Chia thanh cac cum:
  - `data_collector`: parse va import CSV
  - `noise_filter`: kiem tra null, range, duplicate, gap, reset, outlier, tong hop quality report
  - `baseline`: group, tinh thong ke, danh gia confidence, persist baseline
  - `impact`: quan ly event, resolve window, load mau truoc/sau, test thong ke, classify ket qua

### 3.5 `src/rkaa/presentation/api/`

- Day la tang HTTP API.
- Moi file map tu request JSON sang domain/service va map ket qua domain thanh response model.

### 3.6 `tests/`

- `unit/`: test tung ham, model, repository, validator
- `integration/`: test API va luong xu ly voi database test
- `fixtures/`: CSV mau

## 4. Mo hinh du lieu hien tai

### 4.1 `NetworkElement`

File: [src/rkaa/infrastructure/data_store/models/network_element.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/infrastructure/data_store/models/network_element.py:1)

- Bang: `network_elements`
- PK: `ne_id`
- Thuoc tinh:
  - `ne_name`, `vendor`, `technology`, `region`, `site_id`
  - `metadata_json`
- Rang buoc:
  - `technology` chi duoc `LTE | NR | NSA`

### 4.2 `KPIDefinition`

File: [src/rkaa/infrastructure/data_store/models/kpi_definition.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/infrastructure/data_store/models/kpi_definition.py:1)

- Bang: `kpi_definitions`
- PK: `kpi_name`
- Thuoc tinh:
  - `display_name`, `unit`, `description`, `formula`
  - `direction_preference`
  - `warning_threshold`, `critical_threshold`
  - `data_type`
  - `valid_min`, `valid_max`
- Rang buoc:
  - `direction_preference` chi duoc:
    - `higher_is_better`
    - `lower_is_better`
    - `context_dependent`
  - `data_type` chi duoc `kpi | counter`
  - `warning_threshold` va `critical_threshold` khong trung nhau neu cung ton tai

### 4.3 `KPIRecord`

File: [src/rkaa/infrastructure/data_store/models/kpi_record.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/infrastructure/data_store/models/kpi_record.py:1)

- Bang: `kpi_records`
- PK: `id`
- Thuoc tinh:
  - `ne_id`, `kpi_name`
  - `start_time`, `end_time`
  - `value`
  - `quality_flag`
  - `is_noise`
  - `noise_reason`
- Rang buoc:
  - `end_time > start_time`
  - unique theo `(ne_id, kpi_name, start_time)`

### 4.4 `ImpactEvent`

File: [src/rkaa/infrastructure/data_store/models/impact_event.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/infrastructure/data_store/models/impact_event.py:1)

- Bang: `impact_events`
- PK: `id`
- Thuoc tinh:
  - `ne_id`
  - `t1`, `t2`
  - `impact_type`, `description`, `operator`
  - `source`, `status`
  - `created_at`, `updated_at`
- Rang buoc:
  - `source`: `manual | cli | imported`
  - `status`: `draft | confirmed | analyzed | cancelled`
  - neu co `t2` thi `t2 > t1`

### 4.5 `Baseline`

File: [src/rkaa/infrastructure/data_store/models/baseline.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/infrastructure/data_store/models/baseline.py:1)

- Bang: `baselines`
- PK: `id`
- Unique theo `(ne_id, kpi_name, day_period, week_profile)`
- Luu cac thong ke:
  - `mean_value`, `median_value`, `std_value`
  - `p5_value`, `p95_value`
  - `sample_count`
  - `clean_day_count`, `required_day_count`
  - `confidence_status`
  - `computed_at`

### 4.6 `ImpactAnalysis` va `KPIDelta`

File: [src/rkaa/infrastructure/data_store/models/impact_analysis.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/infrastructure/data_store/models/impact_analysis.py:1)

- `impact_analyses`
  - `impact_event_id`
  - `analyzed_at`
  - `analysis_window`
  - `summary` JSON
  - `overall_assessment`
- `kpi_deltas`
  - `analysis_id`
  - `kpi_name`
  - `pre_mean`, `post_mean`
  - `delta_abs`, `delta_pct`
  - `p_value`
  - `change_direction`
  - `anomaly_flag`

### 4.7 `MaintenanceWindow`

File: [src/rkaa/infrastructure/data_store/models/maintenance_window.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/infrastructure/data_store/models/maintenance_window.py:1)

- Bang: `maintenance_windows`
- Thuoc tinh:
  - `ne_id`
  - `start_time`, `end_time`
  - `event_type`, `description`, `created_by`

## 5. Luong khoi dong ung dung

File trung tam: [src/rkaa/main.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/main.py:1)

Thu tu khoi dong:

1. `load_settings()` doc [configs/config.yaml](/C:/Users/quang/Desktop/thuc%20tap/RKAA/configs/config.yaml:1)
2. `configure_logging(settings.logging.level)` cau hinh root logger JSON
3. tao `FastAPI(title=settings.app.name)`
4. gan `app.state.settings = settings`
5. `register_error_handlers(app)` de chuan hoa loi
6. add `CorrelationIdMiddleware`
7. `include_router(...)` cho toan bo API

### 5.1 Middleware correlation id

- Moi request:
  - doc header `X-Correlation-ID`
  - neu khong co thi tao ID moi bang `uuid4`
  - luu vao `ContextVar`
  - sau khi xu ly xong thi them lai vao response header

Tac dung:
- log co the trace theo request
- loi tra ve client cung co `correlation_id`

### 5.2 Error handling

Moi exception duoc map thanh JSON co dang:

```json
{
  "error_code": "...",
  "message": "...",
  "correlation_id": "...",
  "details": {}
}
```

Mapping chinh:
- `RequestValidationError` -> `422 VALIDATION_ERROR`
- `AppError` -> `404` neu `NOT_FOUND`, nguoc lai `400`
- `HTTPException` -> giu nguyen status code
- exception khac -> `500 INTERNAL_ERROR`

## 6. Luong dieu khien theo tung API

## 6.1 Health check

Endpoint: `GET /health`

Luong:
1. FastAPI goi ham `health()`
2. ghi log `health check ok`
3. tra `{"status": "ok"}`

Vai tro:
- xac nhan app dang boot duoc
- test nhanh middleware va logging

## 6.2 KPI CSV Import

Endpoint: `POST /api/v1/kpi-records/import`

File lien quan:
- [src/rkaa/presentation/api/kpi_import.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/presentation/api/kpi_import.py:1)
- [src/rkaa/domain/data_collector/csv_parser.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/domain/data_collector/csv_parser.py:1)
- [src/rkaa/domain/data_collector/import_service.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/domain/data_collector/import_service.py:1)

Luong chi tiet:

1. API doc raw body bytes
2. `parse_kpi_csv_bytes(...)`
3. parser:
   - decode `utf-8-sig`
   - doc `csv.DictReader`
   - kiem tra du cot bat buoc
   - bo qua dong rong
   - validate tung dong bang Pydantic `KPIInputRow`
4. neu parse loi:
   - API doi thanh `AppError(INVALID_INPUT)`
5. neu parse thanh cong:
   - `import_kpi_rows(rows)`
6. import service:
   - tao `KPIImportSummary`
   - mo `session_scope()`
   - insert theo batch
   - neu batch bi `IntegrityError`, fallback insert tung row
   - tach `duplicate` ra khoi `invalid`
7. tra ket qua:
   - `total`
   - `inserted`
   - `duplicates`
   - `invalid`

Diem dang chu y:
- duplicate duoc phat hien chu yeu o tang DB nhan unique constraint
- service chua enrich `NetworkElement` hay `KPIDefinition`
- API nhan raw CSV body, khong phai multipart file

## 6.3 Data Quality Report

Endpoint: `POST /api/v1/data-quality/report`

File lien quan:
- [src/rkaa/presentation/api/data_quality_report.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/presentation/api/data_quality_report.py:1)
- [src/rkaa/domain/noise_filter/data_quality_report.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/domain/noise_filter/data_quality_report.py:1)

Luong chi tiet:

1. API nhan danh sach `records` va `kpi_definition`
2. map request payload thanh `DataQualityRecord` va `DataQualityKPIDefinition`
3. goi `build_data_quality_report(...)`
4. ham tong hop chay cac checker:
   - `detect_duplicate_records`
   - `detect_null_sentinel`
   - `validate_value_range`
   - `detect_time_series_gaps`
   - `detect_counter_resets`
   - `detect_iqr_outliers`
5. tong hop thanh cac chi so:
   - `completeness`
   - `missing_intervals`
   - `duplicate_count`
   - `invalid_count`
   - `noise_ratio`
   - `counter_reset_count`
6. API tra response schema co cung cac truong tren

Y nghia logic:
- `invalid` la null/sentinel/range loi
- `noise_ratio` la hop cua invalid + duplicate + reset + outlier
- `completeness` = `records_thuc_te / (records_thuc_te + missing_intervals)`

## 6.4 Baseline computation

Endpoints:
- `POST /api/v1/baselines/compute`
- `GET /api/v1/baselines/{ne_id}/{kpi_name}`

File lien quan:
- [src/rkaa/presentation/api/baseline.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/presentation/api/baseline.py:1)
- [src/rkaa/domain/baseline_service.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/domain/baseline_service.py:1)
- [src/rkaa/domain/day_period_classifier.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/domain/day_period_classifier.py:1)
- [src/rkaa/domain/week_profile_classifier.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/domain/week_profile_classifier.py:1)
- [src/rkaa/domain/baseline_statistics.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/domain/baseline_statistics.py:1)
- [src/rkaa/domain/baseline_confidence.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/domain/baseline_confidence.py:1)

Luong `POST /compute`:

1. API nhan list clean record
2. mo `session_scope()`
3. tao `BaselineRepository`
4. goi `compute_and_store_baselines(...)`
5. service:
   - group record theo:
     - `ne_id`
     - `kpi_name`
     - `day_period`
     - `week_profile`
   - `day_period` lay tu config
   - `week_profile` = `weekday` hoac `weekend`
   - tinh thong ke:
     - mean, median, std, p5, p95, sample_count
   - danh gia confidence:
     - dem so ngay clean khac nhau
     - so voi `baseline_min_clean_days` hoac tham so override
   - `upsert` vao bang `baselines`
6. API map ORM model thanh response JSON

Luong `GET /{ne_id}/{kpi_name}`:

1. query `BaselineRepository.list_by_ne_kpi`
2. tra toan bo baseline bucket cua KPI do

## 6.5 Impact Event CRUD

Endpoints:
- `POST /api/v1/impacts`
- `GET /api/v1/impacts/{impact_id}`
- `PUT /api/v1/impacts/{impact_id}`
- `DELETE /api/v1/impacts/{impact_id}`

File lien quan:
- [src/rkaa/presentation/api/impact.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/presentation/api/impact.py:1)
- [src/rkaa/domain/impact_service.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/domain/impact_service.py:1)

Luong tao impact:

1. API nhan `ImpactCreateRequest`
2. mo session
3. `NetworkElementRepository.get_by_id(ne_id)` de xac nhan NE ton tai
4. `create_impact_event(...)`
5. service validate `status`
6. create `ImpactEvent`
7. tra response

Luong update impact:

1. API xac dinh field nao thuc su duoc gui len
2. neu co field nghiep vu:
   - goi `update_impact_event(...)`
3. neu co `status`:
   - goi `update_impact_event_status(...)`
4. service enforce state machine:
   - `draft -> confirmed/cancelled`
   - `confirmed -> analyzed/cancelled`
   - `analyzed` khong di tiep
   - `cancelled` khong di tiep

Ghi chu:
- day la lifecycle control quan trong cua impact event
- phan update `t2 = null` duoc xu ly rieng bang `update_t2`

## 6.6 Impact Analysis

Endpoints:
- `POST /api/v1/impacts/{impact_id}/analyze`
- `GET /api/v1/analyses/{analysis_id}`

File lien quan:
- [src/rkaa/presentation/api/impact_analysis.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/presentation/api/impact_analysis.py:1)
- [src/rkaa/domain/impact_analysis_service.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/domain/impact_analysis_service.py:1)
- [src/rkaa/domain/impact_data_loader.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/domain/impact_data_loader.py:1)
- [src/rkaa/domain/window_resolver.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/domain/window_resolver.py:1)
- [src/rkaa/domain/delta_calculator.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/domain/delta_calculator.py:1)
- [src/rkaa/domain/welch_test.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/domain/welch_test.py:1)
- [src/rkaa/domain/mann_whitney_test.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/domain/mann_whitney_test.py:1)
- [src/rkaa/domain/impact_classifier.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/domain/impact_classifier.py:1)

Luong `POST /analyze`:

1. API nhan:
   - danh sach `kpi_names`
   - `pre_window_hours`
   - `recovery_buffer_hours`
   - `post_window_hours`
   - `alpha`
   - `primary_test`
2. mo session
3. tao cac repository:
   - `ImpactEventRepository`
   - `ImpactAnalysisRepository`
   - `KPIDefinitionRepository`
   - `KPIRecordRepository`
4. goi `analyze_and_store_impact(...)`

### Ben trong `analyze_and_store_impact(...)`

Cho moi `kpi_name`:

1. lay `impact_event`
2. lay `kpi_definition`
3. `load_impact_kpi_samples(...)`

### Ben trong `load_impact_kpi_samples(...)`

1. `resolve_impact_windows(...)` tao 4 cua so:
   - `pre_window`
   - `impact_window`
   - `recovery_window`
   - `post_window`
2. xac dinh bucket tham chieu cua impact:
   - day period cua `t1`
   - week profile cua `t1`
3. query KPI records cho `pre_window`
4. query KPI records cho `post_window`
5. loc record:
   - phai cung `day_period`
   - phai cung `week_profile`
   - `quality_flag == good`
   - `is_noise == False`
6. tinh `expected_count`
7. tinh `completeness`
8. danh dau `status = ready` neu completeness >= `0.7`, nguoc lai `insufficient`

### Quay lai `_analyze_one_kpi(...)`

1. neu ca pre va post deu co du lieu:
   - `calculate_delta(...)`
2. chay 2 phep kiem dinh:
   - `run_welch_t_test(...)`
   - `run_mann_whitney_u_test(...)`
3. chon `primary_test` lam ket qua chinh
4. `classify_impact(...)`
   - `improved`
   - `degraded`
   - `stable`
   - `insufficient_data`
5. tao:
   - payload luu `KPIDelta`
   - payload summary cho `ImpactAnalysis.summary`

### Ket thuc luong analyze

1. dem tong so classification
2. tao `ImpactAnalysis`
3. bulk insert `KPIDelta`
4. update `ImpactEvent.status = analyzed`
5. tra response gom:
   - thong tin analysis
   - danh sach delta
   - summary JSON

### Logic `overall_assessment`

- neu co bat ky KPI nao `degraded` -> `degraded`
- neu khong, ma co KPI `improved` -> `improved`
- neu tat ca deu `insufficient_data` -> `insufficient_data`
- con lai -> `stable`

## 7. Cac ham domain quan trong va y nghia

### 7.1 `classify_day_period`

- Dua vao timestamp va config
- Phan bucket:
  - `busy`
  - `transition`
  - `off_peak`
- Bat buoc moi timestamp chi match dung 1 bucket

### 7.2 `classify_week_profile`

- `weekday` neu thu 2 den thu 6
- `weekend` neu thu 7, chu nhat
- bat buoc timestamp phai timezone-aware

### 7.3 `detect_time_series_gaps`

- Sap xep theo `start_time`
- Tim khoang nhay lon hon granularity
- Dem so period thieu
- danh dau `is_warning` neu khoang thieu hon 2 gio

### 7.4 `detect_counter_resets`

- Chi ap dung cho KPI co `data_type = counter`
- Neu gia tri giam so voi mau truoc -> reset

### 7.5 `detect_iqr_outliers`

- Dung quy tac Tukey IQR
- Can it nhat 4 diem
- Tra ve score lech khoi fence

### 7.6 `run_welch_t_test`

- Kiem dinh trung binh 2 tap doc lap
- Co tinh `p_value` bang implementation thu cong dua tren incomplete beta
- khong phu thuoc SciPy

### 7.7 `run_mann_whitney_u_test`

- Kiem dinh phi tham so
- Co tie correction
- p-value xap xi normal
- khong phu thuoc SciPy

## 8. Repository pattern dang duoc dung nhu the nao

Moi repository nhan `Session` trong constructor va tap trung vao bang du lieu cua minh.

Pattern chung:

1. API mo `session_scope()`
2. tao repository can dung
3. goi domain service voi repository
4. domain service goi:
   - `get_by_id`
   - `create`
   - `update`
   - `delete`
   - query chuyen biet
5. `session_scope()` commit neu thanh cong, rollback neu loi

Uu diem:
- tach business logic khoi SQLAlchemy chi tiet
- test service de hon bang fake hoac session test

Han che hien tai:
- chua co dependency injection cua FastAPI
- chua co unit-of-work abstraction ro rang
- transaction boundary dang dat tai route layer

## 9. Cau hinh va co che override

File chinh: [src/rkaa/core/config.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/core/config.py:1)

Nguon cau hinh:

1. file `configs/config.yaml`
2. environment variable prefix `RKAA_`

Quy tac env nesting:
- `RKAA_APP__NAME=...`
- `RKAA_DATABASE__URL=...`

Cach parse:
- co bo parser YAML toi gian tu viet
- co deep merge voi env overrides
- validate bang Pydantic `Settings`

Luu y:
- day khong dung PyYAML
- parser YAML hien tai chi phu hop cau truc don gian key-value theo indent

## 10. Logging va kha nang quan sat

File: [src/rkaa/core/logging.py](/C:/Users/quang/Desktop/thuc%20tap/RKAA/src/rkaa/core/logging.py:1)

Dac diem:
- log JSON
- co `timestamp`, `level`, `logger`, `message`, `correlation_id`
- redact message neu co tu khoa nhay cam:
  - `password`
  - `token`
  - `credential`
  - `secret`

Gia tri:
- de grep log
- de trace loi theo request
- de sau nay dua vao ELK, Loki, OpenSearch

## 11. Kiem thu hien tai

Thong ke so bo hien trang:
- khoang `181` file trong `src/` neu tinh ca generated metadata
- `99` file trong `tests/`
- `204` ham test duoc nhan dien bang regex

Loai test dang co:
- unit test cho:
  - config
  - logging
  - parser
  - noise filter
  - temporal classifier
  - model/repository
  - baseline
  - impact
  - impact analysis
- integration test cho:
  - import API
  - data quality API
  - baseline API
  - impact API
  - impact analysis API
  - error handler

Y nghia:
- do phu test cho phan backend hien tai la kha tot so voi scope da implement
- cac pha chua implement thi tat nhien chua co test

## 12. Thuc trang kien truc

### 12.1 Diem manh

- Phan lop kha ro:
  - presentation
  - domain
  - infrastructure
- Business logic tach thanh cac ham nho, de test
- Co error envelope thong nhat
- Co structured logging
- Co repository layer
- Co baseline va impact analysis luon theo huong deterministic, khong phu thuoc package khoa hoc nang

### 12.2 Han che

- Chua co migration tool nhu Alembic
- Chua co startup hook de tao bang tu dong
- Chua co auth, RBAC, audit
- Chua co async DB, hien tai la sync SQLAlchemy
- Chua co dependency injection cho session/repository
- Chua co report/export runtime du dung theo SRS
- Chua co anomaly detection phase 08 tro di
- parser YAML tu viet co gioi han tinh nang
- import API nhan raw body, chua than thien bang upload form file

## 13. Luong nghiep vu tong hop tu dau den cuoi

### 13.1 Luong 1: Dua KPI vao he thong

1. client gui CSV vao `/api/v1/kpi-records/import`
2. he thong parse va validate contract
3. insert vao `kpi_records`
4. duplicate bi bo qua

### 13.2 Luong 2: Danh gia chat luong du lieu

1. client gui danh sach KPI records va KPI definition
2. he thong chay bo quality checks
3. tra metric chat luong de quyet dinh du lieu co tin cay khong

### 13.3 Luong 3: Tao baseline

1. client cung cap clean records
2. he thong group theo khung thoi gian va loai ngay
3. tinh thong ke baseline
4. luu vao bang `baselines`

### 13.4 Luong 4: Quan ly impact event

1. tao impact event cho NE
2. cap nhat trang thai theo state machine
3. su dung event do lam tam phan tich

### 13.5 Luong 5: Phan tich impact

1. chon impact event
2. chon KPI can danh gia
3. resolve pre/post window
4. lay mau pre va post
5. loc bucket giong impact time
6. tinh delta
7. chay kiem dinh thong ke
8. classify improved/degraded/stable
9. luu ket qua vao `impact_analyses` va `kpi_deltas`
10. doi status impact thanh `analyzed`

## 14. Route thuc te cua du an hien tai

Neu chay dung app trong repo nay, Swagger se gom cac route chinh sau:

- `GET /health`
- `POST /api/v1/kpi-records/import`
- `POST /api/v1/data-quality/report`
- `POST /api/v1/baselines/compute`
- `GET /api/v1/baselines/{ne_id}/{kpi_name}`
- `POST /api/v1/impacts`
- `GET /api/v1/impacts/{impact_id}`
- `PUT /api/v1/impacts/{impact_id}`
- `DELETE /api/v1/impacts/{impact_id}`
- `POST /api/v1/impacts/{impact_id}/analyze`
- `GET /api/v1/analyses/{analysis_id}`

Khong co route:
- export pptx
- export html
- parse docx
- chart recruitment

Neu thay cac route do trong `/docs` thi ban dang mo mot app khac, khong phai RKAA nay.

## 15. Ket luan

Ma nguon hien tai dang la mot backend phan tich KPI co nen tang kha sach va da di het:

- foundation
- data model
- import
- data quality
- temporal classification
- baseline
- impact lifecycle
- impact analysis

Tinh den hien tai, repo da co kha nang xu ly du lieu KPI va phan tich tac dong co y nghia nghiep vu, nhung chua buoc sang cac pha:

- anomaly detection
- reporting/export dung nghia
- frontend
- security
- production hardening day du

Noi cach khac, day la mot backend core kha tot cho pha MVP ky thuat, chua phai san pham hoan chinh theo toan bo SRS.
