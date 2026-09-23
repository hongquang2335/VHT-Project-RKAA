# Prompt 11 - kpi-record-model

Muc tieu duy nhat: tao model KPIRecord.

Fields:
id
ne_id
kpi_name
start_time
end_time
value
quality_flag
is_noise
noise_reason

Quy tac:
- luu UTC;
- end_time > start_time;
- unique theo ne_id + kpi_name + start_time;
- value phai la so.

Chi tao model, migration va test.
