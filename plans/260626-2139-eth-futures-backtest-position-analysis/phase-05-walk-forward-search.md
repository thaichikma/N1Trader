---
phase: 5
title: "Walk-Forward Search"
status: pending
priority: P2
effort: ""
dependencies: [4]
---

# Phase 5: Walk-Forward Search

## Overview
Harness tìm kiếm chiến lược (mục tiêu #1): quét grid tham số EMA+filter qua walk-forward (rolling train/test), chọn tham số tốt nhất trong train, đo trên test (OOS), báo cáo IS vs OOS để lộ overfit.

## Requirements
- Functional:
<!-- Updated: Validation Session 1 - grid chốt: EMA fast{9,12,21} slow{26,50,100,200}, ADX>{20,25}, ATR-regime -->
  - Sinh grid tham số (Validation #2): EMA fast {9,12,21} × slow {26,50,100,200} (chỉ giữ fast<slow), filter ADX>{20,25} on/off, ATR-regime on/off. (+ hệ số SL/TP ATR nếu muốn sweep.)
  - Cắt dữ liệu thành cửa sổ rolling/anchored: train → test → roll.
  - Mỗi cửa sổ: chạy mọi tổ hợp trên train (qua runner P3), chọn best theo metric (vd Sharpe/PF/expectancy), chạy best trên test.
  - Tổng hợp OOS chuỗi test → equity OOS, bảng IS vs OOS mỗi cửa sổ.
  - Xuất kết quả search ra parquet cho dashboard (P6).
- Non-functional: chạy song song được (đa tổ hợp); ghi log tiến độ; tránh giữ toàn bộ trong RAM.

## Architecture
```
n1trader/optimize/
  grid.py          — sinh không gian tham số
  windows.py       — cắt cửa sổ walk-forward (anchored/rolling)
  walk_forward.py  — vòng train/select/test, gom IS/OOS, xuất parquet
  metrics.py       — Sharpe/PF/expectancy/maxDD trên equity (dùng lại quantstats nếu hợp)
```
- Cảnh báo hiệu năng: grid × windows × runner trên 1m có thể nặng → chạy song song (multiprocessing) + thu hẹp grid hợp lý; log rõ số tổ hợp đã chạy/bỏ.

## Related Code Files
- Create: `n1trader/optimize/grid.py`, `n1trader/optimize/windows.py`, `n1trader/optimize/walk_forward.py`, `n1trader/optimize/metrics.py`, `tests/optimize/*`
- Modify: —

## TDD — Tests First
1. `test_grid.py`: spec → đúng số tổ hợp, không trùng, tôn trọng on/off.
2. `test_windows.py`: chuỗi thời gian → cửa sổ train/test không chồng lấn sai cách, đúng số cửa sổ, OOS phủ hết test.
3. `test_metrics.py`: equity biết trước → Sharpe/PF/maxDD đúng giá trị.
4. `test_walk_forward.py` (integration nhỏ, grid 2-3 tổ hợp, 2 cửa sổ, fixture mini): chọn đúng best theo metric trong train, sinh bảng IS/OOS, không rò rỉ test vào train (no leakage).

## Implementation Steps
1. Viết tests (đỏ).
2. `grid.py` → pass test 1.
3. `windows.py` → pass test 2.
4. `metrics.py` → pass test 3.
5. `walk_forward.py` (ghép, song song hoá, xuất parquet) → pass test 4.

## Success Criteria
- [ ] Tests phase 5 xanh.
- [ ] No leakage: tham số chọn từ train, đo trên test — có test khẳng định.
- [ ] Sinh bảng IS vs OOS + equity OOS, lưu parquet.
- [ ] Chạy song song, có log tiến độ + ghi rõ tổ hợp bị bỏ (nếu cap).

## Risk Assessment
- Overfit do grid quá rộng → walk-forward + báo cáo IS/OOS là cơ chế phát hiện; khuyến nghị giữ grid vừa phải.
- Hiệu năng (cảnh báo từ brainstorm) → song song + cân nhắc thu hẹp grid; đo thời gian 1 cửa sổ trước khi chạy full.
- Metric chọn sai hướng (vd chỉ Sharpe) → cho phép cấu hình metric, mặc định kết hợp PF+expectancy.
