# Prompt 04 - global-exceptions

Muc tieu duy nhat: chuan hoa loi API.

Duoc phep sua:
src/rkaa/core/exceptions.py
src/rkaa/core/error_handlers.py
src/rkaa/main.py
tests/integration/test_error_handlers.py

Response loi chuan:
{ error_code, message, correlation_id, details }

Test:
- validation error;
- not found;
- internal error;
- correlation ID ton tai.

Cap nhat tien do va dung.
