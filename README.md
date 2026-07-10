# Báo Cáo Tiến Độ Mã Nguồn RKAA

## 1. Tóm Tắt Hiện Trạng

Mã nguồn hiện tại đã hình thành phần backend lõi cho hệ thống RKAA. Các phần đã có tập trung vào thu thập dữ liệu KPI, kiểm tra chất lượng dữ liệu, tính baseline, quản lý sự kiện tác động và phân tích tác động trước/sau sự kiện.

So với kế hoạch hệ thống trong SRS, mã nguồn hiện mới hoàn thành phần nền tảng và các luồng nghiệp vụ backend quan trọng. Các phần như phát hiện bất thường, phân tích xu hướng, kho tri thức, sinh báo cáo, giao diện người dùng, bảo mật và sẵn sàng triển khai production vẫn chưa có trong runtime hiện tại.

Đánh giá ngắn gọn: mã nguồn hiện tại phù hợp để xem là backend core đang phát triển tốt, nhưng chưa đủ để nghiệm thu như một hệ thống hoàn chỉnh theo toàn bộ SRS.

## 2. Tiến Độ Theo Hạng Mục Hệ Thống

| Hạng mục hệ thống | Trạng thái mã nguồn | Nhận xét |
| --- | --- | --- |
| Nền tảng backend | Đã có | Có FastAPI app, cấu hình, logging, error handling, session DB |
| Data model và repository | Đã có | Các entity chính đã có model và repository |
| Import KPI CSV | Đã có | Có parser, validator, import service và API |
| Data quality | Đã có | Có kiểm tra null, range, duplicate, gap, counter reset, outlier |
| Phân loại thời gian | Đã có | Có day period và week profile classifier |
| Baseline | Đã có | Có tính thống kê, confidence, lưu và truy vấn baseline |
| Impact lifecycle | Đã có | Có CRUD impact event và kiểm soát trạng thái |
| Impact analysis | Đã có | Có load mẫu pre/post, delta, statistical test, classification |
| Anomaly detection | Chưa có trong runtime | Chưa thấy module detector trong `src/rkaa` |
| Trend analysis | Chưa có trong runtime | Chưa có linear trend, trend classifier, STL |
| Knowledge base | Chưa có trong runtime | Chưa có model/API/repository cho knowledge |
| Report/export | Chưa có trong runtime | Chưa có HTML/PDF/Excel report generator |
| Frontend | Chưa có trong runtime | Repo hiện là backend, chưa có UI |
| Security | Chưa có trong runtime | Chưa có user/auth/JWT/RBAC/audit |
| Production readiness | Chưa đầy đủ | Chưa có cấu hình production hoàn chỉnh, init DB cần làm rõ |

## 3. Phạm Vi Đã Có Trong Mã Nguồn

### 3.1 Nền Tảng Backend

Mã nguồn đã có:

- FastAPI application entrypoint tại `src/rkaa/main.py`
- Health check endpoint `GET /health`
- Typed config loader từ `configs/config.yaml`
- Env override với prefix `RKAA_`
- Structured JSON logging
- Correlation ID middleware
- Global error handler
- Database session lifecycle qua `session_scope()`

Kết quả:

- Ứng dụng có nền tảng API ổn định để tiếp tục mở rộng.
- Lỗi API được chuẩn hóa về cùng một dạng JSON.
- Log có correlation ID để hỗ trợ truy vết request.

### 3.2 Data Model Và Persistence

Các model chính đã có:

- `NetworkElement`
- `KPIDefinition`
- `KPIRecord`
- `ImpactEvent`
- `ImpactAnalysis`
- `KPIDelta`
- `Baseline`
- `MaintenanceWindow`

Các repository chính đã có:

- Network element repository
- KPI definition repository
- KPI record repository
- Impact event repository
- Impact analysis repository
- Baseline repository
- Maintenance window repository

Nhận xét:

- Tầng persistence đang theo pattern rõ ràng: SQLAlchemy model, repository và session do caller quản lý.
- Các ràng buộc quan trọng như unique key, check constraint và time window constraint đã được khai báo.

### 3.3 Import KPI CSV

Năng lực đã có:

- Định nghĩa schema dòng KPI input
- Validate timestamp bắt buộc có timezone
- Validate các cột bắt buộc
- Parse CSV từ bytes hoặc file path
- Import vào bảng `kpi_records`
- Bỏ qua duplicate dựa trên unique constraint
- API import KPI

Endpoint:

```text
POST /api/v1/kpi-records/import
```

Output chính:

```json
{
  "total": 2,
  "inserted": 2,
  "duplicates": 0,
  "invalid": 0
}
```

Nhận xét:

- Luồng import đã đủ dùng cho backend MVP.
- API hiện nhận raw CSV body, chưa phải multipart upload.

### 3.4 Data Quality

Năng lực đã có:

- Phát hiện null/sentinel value
- Validate value theo `valid_min` và `valid_max`
- Phát hiện duplicate trong batch
- Phát hiện gap trong time series
- Phát hiện counter reset
- Phát hiện IQR outlier
- Tổng hợp data quality report

Endpoint:

```text
POST /api/v1/data-quality/report
```

Output chính:

```json
{
  "completeness": 0.8,
  "missing_intervals": 1,
  "duplicate_count": 0,
  "invalid_count": 0,
  "noise_ratio": 0.0,
  "counter_reset_count": 0
}
```

Nhận xét:

- Đây là phần quan trọng vì baseline và impact analysis phụ thuộc vào dữ liệu sạch.
- Service hiện tính toán trên payload đầu vào, chưa tự động đọc toàn bộ dữ liệu từ DB theo query nghiệp vụ.

### 3.5 Phân Loại Thời Gian Và Maintenance

Năng lực đã có:

- Classify timestamp vào `busy`, `transition`, `off_peak`
- Classify timestamp vào `weekday`, `weekend`
- Maintenance window model và repository
- Logic đánh dấu KPI record overlap với maintenance window

Nhận xét:

- Cấu hình day period nằm trong `configs/config.yaml`.
- Logic day period có hỗ trợ khoảng thời gian qua nửa đêm.
- Đây là nền cho baseline theo bucket và impact comparison đúng ngữ cảnh thời gian.

### 3.6 Baseline

Năng lực đã có:

- Group sample theo `ne_id`, `kpi_name`, `day_period`, `week_profile`
- Tính `mean`, `median`, `std`, `p5`, `p95`
- Đánh giá confidence theo số ngày dữ liệu sạch
- Lưu baseline vào DB bằng upsert
- API compute và API retrieve baseline

Endpoint:

```text
POST /api/v1/baselines/compute
GET /api/v1/baselines/{ne_id}/{kpi_name}
```

Output chính:

```json
{
  "baselines": [
    {
      "ne_id": "NE001",
      "kpi_name": "availability",
      "day_period": "busy",
      "week_profile": "weekday",
      "mean_value": 99.1,
      "median_value": 99.2,
      "std_value": 0.2,
      "p5_value": 98.8,
      "p95_value": 99.4,
      "sample_count": 4,
      "clean_day_count": 1,
      "required_day_count": 14,
      "confidence_status": "insufficient",
      "computed_at": "2026-07-10T09:00:00+07:00"
    }
  ]
}
```

Nhận xét:

- Baseline đã có logic nghiệp vụ cốt lõi.
- API compute hiện nhận records trong request, chưa phải luồng production tự query dữ liệu lịch sử từ DB.

### 3.7 Impact Lifecycle

Năng lực đã có:

- Tạo impact event
- Lấy impact event theo id
- Cập nhật impact event
- Xóa impact event
- Kiểm soát chuyển trạng thái
- Resolve các time window pre/impact/recovery/post

Endpoint:

```text
POST /api/v1/impacts
GET /api/v1/impacts/{impact_id}
PUT /api/v1/impacts/{impact_id}
DELETE /api/v1/impacts/{impact_id}
```

State machine hiện có:

```text
draft -> confirmed
draft -> cancelled
confirmed -> analyzed
confirmed -> cancelled
```

Output chính khi tạo impact:

```json
{
  "id": 1,
  "ne_id": "NE001",
  "t1": "2026-07-10T09:00:00+07:00",
  "t2": "2026-07-10T10:00:00+07:00",
  "impact_type": "maintenance",
  "description": "Planned parameter change",
  "operator": "operator_a",
  "source": "manual",
  "status": "confirmed"
}
```

Nhận xét:

- Impact lifecycle đã có khung nghiệp vụ rõ.
- Khi analysis hoàn thành, impact event có thể được chuyển sang `analyzed`.

### 3.8 Impact Analysis

Năng lực đã có:

- Load KPI sample trước và sau impact event
- Lọc sample theo day period và week profile của impact
- Chỉ dùng sample sạch: `quality_flag == good` và `is_noise == false`
- Tính completeness cho pre/post window
- Tính delta tuyệt đối và delta phần trăm
- Chạy Welch's t-test
- Chạy Mann-Whitney U test
- Phân loại kết quả theo direction preference của KPI
- Lưu `ImpactAnalysis` và `KPIDelta`

Endpoint:

```text
POST /api/v1/impacts/{impact_id}/analyze
GET /api/v1/analyses/{analysis_id}
```

Output chính:

```json
{
  "id": 1,
  "impact_event_id": 1,
  "analyzed_at": "2026-07-10T11:00:00+07:00",
  "analysis_window": "pre=2h,recovery=1h,post=2h",
  "overall_assessment": "degraded",
  "deltas": [
    {
      "id": 1,
      "analysis_id": 1,
      "kpi_name": "availability",
      "pre_mean": 99.2,
      "post_mean": 97.8,
      "delta_abs": -1.4,
      "delta_pct": -1.41,
      "p_value": 0.03,
      "change_direction": "decrease",
      "anomaly_flag": "not_evaluated"
    }
  ]
}
```

Nhận xét:

- Đây là phần nghiệp vụ sâu nhất hiện có trong backend.
- `anomaly_flag` hiện mới ở mức `not_evaluated`, vì anomaly detection chưa được implement.

## 4. Input Và Output Của Hệ Thống Hiện Tại

### 4.1 Input CSV KPI

API import KPI nhận raw CSV body.

Ví dụ input:

```csv
timestamp,period_end,ne_id,kpi_name,value,unit,quality_flag
2026-07-10T08:00:00+07:00,2026-07-10T08:15:00+07:00,NE001,availability,99.1,%,good
2026-07-10T08:15:00+07:00,2026-07-10T08:30:00+07:00,NE001,availability,99.3,%,good
```

Ví dụ output:

```json
{
  "total": 2,
  "inserted": 2,
  "duplicates": 0,
  "invalid": 0
}
```

### 4.2 Input Data Quality

Ví dụ input:

```json
{
  "records": [
    {
      "ne_id": "NE001",
      "kpi_name": "availability",
      "start_time": "2026-07-10T08:00:00+07:00",
      "value": 99.1
    },
    {
      "ne_id": "NE001",
      "kpi_name": "availability",
      "start_time": "2026-07-10T08:15:00+07:00",
      "value": 99.3
    }
  ],
  "kpi_definition": {
    "data_type": "kpi",
    "valid_min": 0,
    "valid_max": 100
  },
  "granularity_minutes": 15,
  "iqr_multiplier": 1.5,
  "sentinel_values": []
}
```

Ví dụ output:

```json
{
  "completeness": 1.0,
  "missing_intervals": 0,
  "duplicate_count": 0,
  "invalid_count": 0,
  "noise_ratio": 0.0,
  "counter_reset_count": 0
}
```

### 4.3 Input Baseline

Ví dụ input:

```json
{
  "records": [
    {
      "ne_id": "NE001",
      "kpi_name": "availability",
      "start_time": "2026-07-10T08:00:00+07:00",
      "value": 99.1
    },
    {
      "ne_id": "NE001",
      "kpi_name": "availability",
      "start_time": "2026-07-10T08:15:00+07:00",
      "value": 99.3
    }
  ],
  "required_clean_days": 14,
  "computed_at": "2026-07-10T09:00:00+07:00"
}
```

Ví dụ output:

```json
{
  "baselines": [
    {
      "ne_id": "NE001",
      "kpi_name": "availability",
      "day_period": "busy",
      "week_profile": "weekday",
      "mean_value": 99.2,
      "median_value": 99.2,
      "std_value": 0.1,
      "p5_value": 99.11,
      "p95_value": 99.29,
      "sample_count": 2,
      "clean_day_count": 1,
      "required_day_count": 14,
      "confidence_status": "insufficient",
      "computed_at": "2026-07-10T09:00:00+07:00"
    }
  ]
}
```

### 4.4 Input Impact Event

Ví dụ input:

```json
{
  "ne_id": "NE001",
  "t1": "2026-07-10T09:00:00+07:00",
  "t2": "2026-07-10T10:00:00+07:00",
  "impact_type": "maintenance",
  "description": "Planned parameter change",
  "operator": "operator_a",
  "source": "manual",
  "status": "confirmed"
}
```

Ví dụ output:

```json
{
  "id": 1,
  "ne_id": "NE001",
  "t1": "2026-07-10T09:00:00+07:00",
  "t2": "2026-07-10T10:00:00+07:00",
  "impact_type": "maintenance",
  "description": "Planned parameter change",
  "operator": "operator_a",
  "source": "manual",
  "status": "confirmed"
}
```

### 4.5 Input Impact Analysis

Ví dụ input:

```json
{
  "kpi_names": ["availability"],
  "pre_window_hours": 2,
  "recovery_buffer_hours": 1,
  "post_window_hours": 2,
  "alpha": 0.05,
  "primary_test": "welch",
  "analyzed_at": "2026-07-10T11:00:00+07:00"
}
```

Ví dụ output:

```json
{
  "id": 1,
  "impact_event_id": 1,
  "analyzed_at": "2026-07-10T11:00:00+07:00",
  "analysis_window": "pre=2h,recovery=1h,post=2h",
  "summary": {
    "primary_test": "welch",
    "classification_counts": {
      "degraded": 1
    }
  },
  "overall_assessment": "degraded",
  "deltas": [
    {
      "id": 1,
      "analysis_id": 1,
      "kpi_name": "availability",
      "pre_mean": 99.2,
      "post_mean": 97.8,
      "delta_abs": -1.4,
      "delta_pct": -1.41,
      "p_value": 0.03,
      "change_direction": "decrease",
      "anomaly_flag": "not_evaluated"
    }
  ]
}
```

## 5. Phạm Vi Chưa Có Trong Runtime

### 5.1 Anomaly Detection

Chưa thấy module runtime cho:

- Threshold detector
- Z-score detector
- Three-sigma detector
- Anomaly aggregation
- Gắn anomaly với impact analysis

Tác động:

- Hệ thống hiện chưa tự động đánh dấu anomaly trên KPI.
- Impact analysis hiện mới đánh giá thay đổi trước/sau, chưa tích hợp kết quả anomaly.

### 5.2 Trend Analysis

Chưa thấy module runtime cho:

- Linear trend
- Trend classifier
- STL decomposition

Tác động:

- Hệ thống chưa đánh giá xu hướng dài hạn của KPI.

### 5.3 Knowledge Base

Chưa thấy module runtime cho:

- Knowledge entry model
- Knowledge repository
- Versioning
- Approval workflow
- Knowledge API
- Knowledge enricher

Tác động:

- Hệ thống chưa có lớp tri thức để giải thích nguyên nhân, khuyến nghị xử lý hoặc bổ sung ngữ cảnh.

### 5.4 Report Và Export

Chưa thấy module runtime cho:

- Report data model
- HTML report
- Chart integration
- Excel report
- PDF report
- Report API

Tác động:

- Hệ thống chưa sinh báo cáo nghiệp vụ đúng nghĩa.
- Trong mã nguồn hiện tại không có chức năng `export pptx`.
- Trong SRS hiện tại, các định dạng báo cáo được nhắc tới là HTML/PDF/Excel, không phải PPTX.

### 5.5 Frontend

Chưa thấy mã nguồn frontend runtime.

Tác động:

- Người dùng hiện chỉ có thể thao tác qua API/Swagger hoặc HTTP client.
- Chưa có dashboard, import page, impact page, analysis page, knowledge page.

### 5.6 Security Và Audit

Chưa thấy module runtime cho:

- User model
- Password authentication
- JWT authentication
- RBAC
- Audit log
- Audit middleware
- API security

Tác động:

- Hệ thống chưa sẵn sàng cho môi trường có nhiều người dùng hoặc dữ liệu nhạy cảm.
- Chưa có kiểm soát truy cập theo vai trò.

## 6. API Runtime Hiện Có

Khi chạy đúng ứng dụng RKAA, Swagger của hệ thống sẽ có các route chính:

```text
GET    /health
POST   /api/v1/kpi-records/import
POST   /api/v1/data-quality/report
POST   /api/v1/baselines/compute
GET    /api/v1/baselines/{ne_id}/{kpi_name}
POST   /api/v1/impacts
GET    /api/v1/impacts/{impact_id}
PUT    /api/v1/impacts/{impact_id}
DELETE /api/v1/impacts/{impact_id}
POST   /api/v1/impacts/{impact_id}/analyze
GET    /api/v1/analyses/{analysis_id}
```

Lệnh chạy để quan sát đúng app RKAA:

```powershell
uv run uvicorn --app-dir src rkaa.main:app --reload --port 8010
```

Swagger:

```text
http://127.0.0.1:8010/docs
```

Lưu ý:

- Nếu Swagger hiện các route như `/api/export/pptx`, `/api/parse-docx`, `/api/chart/recruitment` thì đó không phải ứng dụng RKAA trong mã nguồn hiện tại.
- Nên dùng cổng riêng `8010` khi kiểm tra để tránh nhầm với ứng dụng khác đang chạy ở `8000`.

## 7. Thư Viện Và Nền Tảng Đang Dùng

Runtime dependencies:

- `fastapi`
- `pydantic`
- `sqlalchemy`
- `uvicorn[standard]`

Development dependencies:

- `pytest`
- `httpx`
- `coverage`
- `ruff`

Nhận xét:

- Stack hiện tại gọn và phù hợp backend MVP.
- Các statistical test hiện được implement bằng Python standard library, chưa phụ thuộc SciPy.
- `pyproject.toml` đã khai báo các dependency runtime cần thiết, nhưng `uv.lock` cần được đồng bộ lại nếu môi trường cài đặt mới yêu cầu lockfile chính xác.

## 8. Bằng Chứng Kiểm Thử

Các nhóm test hiện có trong repo:

- Unit test cho config, logging, error handling
- Unit test cho model và repository
- Unit test cho CSV parser và import service
- Unit test cho data quality checker
- Unit test cho baseline service
- Unit test cho impact service và impact analysis
- Integration test cho import API
- Integration test cho data quality API
- Integration test cho baseline API
- Integration test cho impact API
- Integration test cho impact analysis API

Một số kết quả kiểm thử gần đây đã ghi nhận:

```text
tests/integration/test_impact_analysis_api.py: 2 passed
Impact regression group: 10 passed
```

Lệnh kiểm thử tham chiếu:

```powershell
uv run pytest --basetemp .tmp/pytest-impact-analysis tests/integration/test_impact_analysis_api.py
uv run pytest --basetemp .tmp/pytest-impact-regression tests/unit/test_impact_analysis_service.py tests/integration/test_impact_api.py tests/unit/test_impact_service.py
```

Lưu ý:

- Trên Windows, nên dùng `--basetemp .tmp/...` để tránh lỗi quyền ghi temp trong một số môi trường.
- Các warning về `.pytest_cache` permission và Starlette deprecation chưa ảnh hưởng đến các test cốt lõi đã chạy.

## 9. Rủi Ro Và Vấn Đề Cần Theo Dõi

### 9.1 Dependency Và Lockfile

Rủi ro:

- `pyproject.toml` đã có dependency runtime cần thiết.
- `uv.lock` có thể cần đồng bộ lại với dependency mới.

Tác động:

- Môi trường mới có thể gặp lỗi thiếu thư viện nếu chưa chạy `uv sync`.
- Cần xác nhận lockfile trước khi bàn giao cho bên kiểm thử độc lập.

### 9.2 Khởi Tạo Database

Rủi ro:

- Source có SQLAlchemy model và session.
- Quy trình tạo schema database trong môi trường mới cần được làm rõ hơn.

Tác động:

- API cần DB sẽ lỗi nếu database chưa có bảng.
- Cần bổ sung hướng dẫn init DB hoặc migration workflow.

### 9.3 Khoảng Trống Chức Năng So Với SRS

Rủi ro:

- Nhiều mảng quan trọng của hệ thống chưa có trong runtime.
- Các phần chưa có gồm anomaly, report, frontend, security và production readiness.

Tác động:

- Chưa đủ điều kiện đánh giá như một sản phẩm hoàn chỉnh.
- Chỉ nên đánh giá theo phạm vi backend core đã implement.

### 9.4 Nhầm Ứng Dụng Khi Kiểm Thử Local

Rủi ro:

- Cổng `8000` có thể đang được ứng dụng khác sử dụng.
- Swagger ở `8000` có thể hiện route không thuộc RKAA.

Tác động:

- Bên đánh giá có thể test nhầm ứng dụng.
- Khuyến nghị chạy RKAA ở `8010` khi review.

## 10. Nhận Định Về Chất Lượng Mã Nguồn

Điểm mạnh:

- Phân lớp API, domain và infrastructure khá rõ.
- Business logic được tách thành module nhỏ, dễ test.
- Repository pattern giúp tách persistence khỏi domain service.
- Có error handling và logging có tính vận hành.
- Các phần đã implement có test unit và integration tương ứng.

Hạn chế:

- Chưa có frontend.
- Chưa có security layer.
- Chưa có report/export runtime.
- Chưa có anomaly detection runtime.
- Chưa có migration/init DB workflow thật rõ.
- Chưa có production deployment package đầy đủ.

Kết luận:

Mã nguồn hiện tại có chất lượng tốt ở phần backend core, nhưng phạm vi chưa đủ để coi là hoàn thành hệ thống. Các thành phần nền tảng đã đủ khả năng làm mốc cho giai đoạn tiếp theo, đặc biệt là anomaly detection và reporting.