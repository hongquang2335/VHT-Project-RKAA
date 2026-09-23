# Prompt 18 - import-service

Muc tieu duy nhat: import du lieu da parse vao database.

Tao:
src/rkaa/domain/data_collector/import_service.py
tests/integration/test_import_service.py

Output:
{ total, inserted, duplicates, invalid }

Yeu cau:
- batch insert;
- skip duplicate;
- transaction an toan;
- khong tao API.
