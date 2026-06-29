---
phase: 6
title: "Streamlit Dashboard"
status: pending
priority: P2
effort: ""
dependencies: [4, 5]
---

# Phase 6: Streamlit Dashboard

## Overview
Dashboard Streamlit đọc position records (P4) + kết quả walk-forward (P5): 4 trang — overview, trades (lọc theo 4 nhãn), classification breakdown, compare (tham số / IS vs OOS).

## Requirements
- Functional:
  - **Overview:** equity curve, drawdown, KPIs (winrate, PF, expectancy, maxDD, tổng phí, số lệnh).
  - **Trades:** bảng vị thế + bộ lọc theo `filter_set / regime / outcome / session / weekday / near_news`; xem chi tiết 1 lệnh (MAE/MFE/R).
  - **Classification:** breakdown hiệu suất theo từng chiều (vd PnL theo regime, winrate theo session) + heatmap chéo 2 chiều.
  - **Compare:** xếp hạng tổ hợp tham số, biểu đồ IS vs OOS, phát hiện overfit.
- Non-functional: đọc parquet (không tính lại backtest trong app); cache dữ liệu; chạy `streamlit run`.

## Architecture
```
n1trader/dashboard/
  app.py            — entry, sidebar điều hướng, nạp + cache parquet
  overview.py       — trang KPIs + equity/drawdown
  trades.py         — bảng + filter 4 nhãn
  classification.py — breakdown + heatmap theo nhãn
  compare.py        — bảng xếp hạng + IS/OOS
  data_access.py    — load records/walk-forward parquet (thuần, test được)
```
- Logic dữ liệu tách vào `data_access.py` để test mà không cần chạy UI.

## Related Code Files
- Create: `n1trader/dashboard/app.py`, `n1trader/dashboard/overview.py`, `n1trader/dashboard/trades.py`, `n1trader/dashboard/classification.py`, `n1trader/dashboard/compare.py`, `n1trader/dashboard/data_access.py`, `tests/dashboard/test_data_access.py`
- Modify: —

## TDD — Tests First
(UI Streamlit không unit-test trực tiếp; test phần logic dữ liệu thuần.)
1. `test_data_access.py`:
   - Load records parquet → KPIs (winrate/PF/expectancy/maxDD/tổng phí) tính đúng trên fixture.
   - Filter theo từng nhãn trả đúng tập con.
   - Breakdown theo chiều (groupby) ra đúng tổng hợp.
   - Đọc walk-forward parquet → bảng IS/OOS đúng.

## Implementation Steps
1. Viết `test_data_access.py` (đỏ).
2. `data_access.py` (KPIs, filter, breakdown, IS/OOS) → pass test.
3. Dựng `app.py` + 4 trang dùng `data_access.py` + plotly.
4. Kiểm thử thủ công: `streamlit run n1trader/dashboard/app.py` trên dữ liệu thật.

## Success Criteria
- [ ] `test_data_access.py` xanh (KPIs/filter/breakdown/IS-OOS đúng).
- [ ] 4 trang chạy được, lọc theo cả 4 nhãn.
- [ ] Overview KPIs khớp account report (P3/P4).
- [ ] Compare hiển thị IS vs OOS từ P5.

## Risk Assessment
- Dữ liệu lớn làm app chậm → cache + đọc parquet theo cột; phân trang bảng trades.
- KPIs lệch định nghĩa với P4/P5 → dùng chung công thức metric (tái dùng `optimize/metrics.py`), tránh trùng lặp (DRY).
- UI không có test tự động → cô lập logic vào `data_access.py`; UI giữ mỏng.
