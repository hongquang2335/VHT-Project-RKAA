# Prompt 02 - config-loader

Muc tieu duy nhat: trien khai cau hinh tu YAML va environment variables.

Duoc phep sua:
configs/config.yaml
src/rkaa/core/config.py
src/rkaa/main.py
tests/unit/test_config.py

Yeu cau:
- Dung typed settings.
- Environment variable co quyen ghi de YAML.
- Khong hardcode database URL, timezone hoac granularity.
- Bao loi ro khi cau hinh khong hop le.
- Khong doc credential vao log.

Test bat buoc:
- load YAML thanh cong;
- environment override;
- thieu field bat buoc;
- kieu du lieu khong hop le.

Cap nhat tien do va dung.
