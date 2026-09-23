# Prompt 16 - input-data-contract

Muc tieu duy nhat: dinh nghia schema du lieu KPI dau vao.

Tao:
docs/input_data_spec.md
src/rkaa/domain/data_collector/schemas.py
tests/unit/test_input_schema.py

Schema CSV bat buoc:
timestamp
period_end
ne_id
kpi_name
value
unit
quality_flag

Quy tac:
- ISO 8601;
- timezone bat buoc;
- period_end > timestamp;
- value parse duoc thanh float;
- ne_id, kpi_name khong rong.

Khong viet parser.
