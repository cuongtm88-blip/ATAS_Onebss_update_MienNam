# ATS OneBSS — Miền Nam

Đây là bản mã nguồn độc lập của ứng dụng Miền Nam, được đồng bộ từ bản phát hành 0.9.86. Mọi code và dữ liệu Miền Nam được quản lý ngay trong thư mục này.

## Cấu hình và dữ liệu

- `config.toml`: OneBSS, Google Sheet, lịch và đường dẫn quy tắc Miền Nam.
- `project_rules_MN.toml`: quy tắc dự án Miền Nam.
- `Giao_phieu_MN.xlsx`: danh sách dịch vụ và quy tắc giao phiếu Miền Nam.
- `attendance_calendar.json`: dữ liệu lịch làm việc cục bộ/cache của Miền Nam.
- `regions.toml`: chỉ khai báo Miền Nam và repository cập nhật riêng.

Không dùng cấu hình, workbook, database hoặc hồ sơ trình duyệt từ thư mục gốc, MB hay MT.

## Kiểm tra và chạy từ mã nguồn

```sh
uv sync --extra dev
uv run pytest
uv run ats-onebss-gui
```

## Đóng gói

- macOS Apple Silicon: `./scripts/build_app.sh`
- Windows x64: `./scripts/build_app.ps1`

Các script chỉ đưa dữ liệu Miền Nam trong thư mục này vào gói ứng dụng.
