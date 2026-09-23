# Prompt 01 - project-skeleton

Muc tieu duy nhat: tao skeleton du an RKAA theo kien truc trong SRS.

Duoc phep tao hoac sua:
pyproject.toml
src/rkaa/__init__.py
src/rkaa/main.py
src/rkaa/core/__init__.py
src/rkaa/domain/__init__.py
src/rkaa/application/__init__.py
src/rkaa/infrastructure/__init__.py
src/rkaa/presentation/__init__.py
tests/conftest.py
README.md

Yeu cau:
- Python 3.11+.
- FastAPI khoi dong duoc.
- Co endpoint GET /health.
- Khong them database.
- Khong them authentication.
- Khong them chuc nang nghiep vu.
- Tao test cho /health.

Definition of Done:
pytest pass
ruff pass
GET /health tra 200

Cap nhat docs/progress va dung.
