# Input Data Specification

## CSV KPI Input Contract

He thong nhan du lieu KPI dau vao theo dang CSV, moi dong bieu dien mot quan sat KPI trong mot khoang thoi gian.

### Required columns

| Column | Type | Rule |
| --- | --- | --- |
| `timestamp` | ISO 8601 datetime | Bat buoc co timezone |
| `period_end` | ISO 8601 datetime | Bat buoc co timezone va lon hon `timestamp` |
| `ne_id` | string | Bat buoc, khong rong sau khi trim |
| `kpi_name` | string | Bat buoc, khong rong sau khi trim |
| `value` | float | Phai parse duoc thanh so thuc |
| `unit` | string | Bat buoc |
| `quality_flag` | string | Bat buoc trong schema CSV |

### Example row

```csv
timestamp,period_end,ne_id,kpi_name,value,unit,quality_flag
2026-07-08T00:00:00+07:00,2026-07-08T00:15:00+07:00,NE-001,erab_success_rate,98.7,percent,good
```

### Validation notes

- `timestamp` va `period_end` phai dung dinh dang datetime ISO 8601 ma Pydantic parse duoc.
- Ca hai truong thoi gian deu phai co offset timezone, vi du `Z` hoac `+07:00`.
- `period_end` phai xay ra sau `timestamp`.
- `value` cho phep duoc truyen vao duoi dang chuoi CSV, nhung phai parse thanh `float`.
- Khong dinh nghia parser o giai doan nay; tai lieu nay chi mo ta contract dau vao.
