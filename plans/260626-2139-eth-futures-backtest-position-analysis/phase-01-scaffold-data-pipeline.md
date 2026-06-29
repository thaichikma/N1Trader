---
phase: 1
title: "Scaffold & Data Pipeline"
status: pending
priority: P1
effort: ""
dependencies: []
---

# Phase 1: Scaffold & Data Pipeline

## Overview
Dựng cấu trúc package Python + pipeline tải OHLCV 1m ETHUSDT Perp (2025→nay), lưu parquet, vá gap, nạp vào Nautilus ParquetDataCatalog, và loader cho bảng datetime news → blackout windows.

## Requirements
- Functional:
  - Tải bulk klines 1m từ `data.binance.vision` (zip theo tháng, futures/um/monthly/klines/ETHUSDT/1m) + vá gap gần đây qua `ccxt`.
  - Lưu raw parquet + nạp `Bar` vào Nautilus `ParquetDataCatalog`.
  - Loader bảng news (CSV) → danh sách window `(start_utc, end_utc)` + mốc cancel-limit (news − 30').
  - Kiểm tra tính liên tục dữ liệu (không thiếu nến, đúng bước 60s).
- Non-functional: idempotent (chạy lại không tải trùng), UTC nhất quán, tải bulk thay vì REST từng trang.

## Architecture
```
n1trader/data/
  downloader.py   — fetch bulk binance.vision + ccxt gap-fill
  catalog.py      — raw parquet -> Nautilus Bar -> ParquetDataCatalog
  news_windows.py — CSV news -> windows + cancel marks
  integrity.py    — kiểm tra gap/continuity
```
- News CSV schema: `datetime_utc, impact, label` (impact để lọc "tin lớn").
- Window = `[news − pre_min, news + post_min]`; cancel mark = `news − 30m` (tham số hoá).

## Related Code Files
- Create: `n1trader/data/downloader.py`, `n1trader/data/catalog.py`, `n1trader/data/news_windows.py`, `n1trader/data/integrity.py`, `pyproject.toml`, `tests/data/*`, `tests/fixtures/news_sample.csv`, `tests/fixtures/klines_sample.parquet`
- Modify: —
- Delete: —

## TDD — Tests First
1. `test_news_windows.py`: CSV mẫu → đúng số window, đúng biên `[pre,post]`, mốc cancel = news−30'. Lọc theo impact.
2. `test_integrity.py`: chuỗi 1m có gap nhân tạo → phát hiện đúng vị trí gap; chuỗi đủ → pass.
3. `test_downloader.py`: mock HTTP/ccxt → ghép bulk + gap không trùng/đè, sắp xếp tăng dần theo time, idempotent.
4. `test_catalog.py`: parquet mẫu → nạp được Bar vào catalog, query trả đúng số nến + timestamp UTC.

## Implementation Steps
1. Viết tests (đỏ) với fixtures nhỏ (vài trăm nến + vài dòng news).
2. `news_windows.py` → pass test 1.
3. `integrity.py` → pass test 2.
4. `downloader.py` (bulk + ccxt gap-fill, idempotent) → pass test 3.
5. `catalog.py` (Bar → ParquetDataCatalog) → pass test 4.
6. `pyproject.toml` + deps; script tải thật cho dải 2025→nay (chạy ngoài test, không nằm trong CI).

## Success Criteria
- [ ] Tests phase 1 xanh.
- [ ] Tải thật ra parquet đủ 2025→nay, integrity pass (0 gap bất thường).
- [ ] Catalog query được Bar 1m theo khoảng thời gian.
- [ ] News CSV → windows + cancel marks đúng.

## Risk Assessment
- Bulk binance.vision đổi đường dẫn/format → cô lập trong `downloader.py`, test bằng mock.
- Lệch timezone → ép UTC mọi nơi, test khẳng định.
- Dữ liệu lớn (~750k nến) → parquet nén, đọc theo cột; tránh giữ toàn bộ trong RAM khi không cần.
