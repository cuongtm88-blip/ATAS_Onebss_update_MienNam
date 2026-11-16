$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path -LiteralPath "Giao_phieu_MN.xlsx")) {
  throw "Không tìm thấy file quy tắc Giao_phieu_MN.xlsx trong thư mục MN."
}

uv sync --extra packaging
uv run pyinstaller `
  --noconfirm `
  --clean `
  --onedir `
  --windowed `
  --name ATS-OneBSS `
  --collect-all playwright `
  --collect-submodules encodings `
  --add-data "regions.toml;." `
  --add-data "config.toml;." `
  --add-data "project_rules_MN.toml;." `
  --add-data "Giao_phieu_MN.xlsx;." `
  --add-data "attendance_calendar.json;." `
  --add-data "assets/vinaphone-logo.png;assets" `
  src/ats_onebss/gui_main.py

$version = uv run python -c "from ats_onebss import __version__; print(__version__)"
Set-Content -LiteralPath "dist/ATS-OneBSS/VERSION.txt" -Value $version -NoNewline -Encoding ascii

Write-Host "Đã tạo ứng dụng trong dist/ATS-OneBSS"
