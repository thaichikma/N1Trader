---
phase: 2
title: "Strategy & Blackout Rules"
status: pending
priority: P1
effort: ""
dependencies: [1]
---

# Phase 2: Strategy & Blackout Rules

## Overview
Triển khai Nautilus `Strategy` cho EMA Cross + filters, và lớp blackout (cuối tuần UTC, news window, cancel limit 30' trước news) thực thi trong `on_bar`. Đảm bảo no look-ahead.

<!-- Updated: Validation Session 1 - entry=market+ATR SL/TP, news window ±30', cancel-limit unit-test only -->
## Requirements
- Functional:
  - EMA fast/slow cross → tín hiệu long/short. Grid (Validation #2): fast {9,12,21}, slow {26,50,100,200}.
  - Filters bật/tắt qua config: **ADX > {20,25}** + **ATR-regime**. (Volume/EMA-slope là tùy chọn mở rộng, không bắt buộc V1.)
  - **Entry = MARKET tại open nến kế tiếp** sau khi nến tín hiệu đóng (no look-ahead).
  - **SL/TP theo ATR:** SL ≈ 1.5×ATR, TP ≈ 2-3×ATR (hệ số tham số hoá). Tính ATR trong strategy, lưu lại SL ban đầu để Phase 4 tính R.
  - Blackout entry: không mở vị thế mới nếu (a) timestamp UTC là Sat/Sun, hoặc (b) trong news window **±30 phút** (Validation #1).
  - `blackout.cancel_due(ts, marks)` (mốc news−30') **được implement cho live tương lai** nhưng vì entry là market nên KHÔNG có limit pending trong backtest → chỉ **unit-test hàm này**, không assert mức engine.
- Non-functional: filter/blackout/signals là thành phần thuần, test được độc lập với engine.

## Architecture
```
n1trader/strategy/
  ema_cross.py  — Strategy: tính EMA, sinh tín hiệu, đặt lệnh
  filters.py    — hàm filter thuần (bar/indicator -> bool), cấu hình bật/tắt
  blackout.py   — is_weekend(ts), in_news_window(ts, windows), cancel_due(ts, marks)
  signals.py    — logic cross + ghép filter (tách khỏi I/O của engine để test)
```
- Blackout dùng windows/marks từ `data/news_windows.py` (Phase 1).
- `signals.py` nhận series indicator → trả tín hiệu, không phụ thuộc Nautilus → test nhanh, no look-ahead kiểm chứng bằng shift.

## Related Code Files
- Create: `n1trader/strategy/ema_cross.py`, `n1trader/strategy/filters.py`, `n1trader/strategy/blackout.py`, `n1trader/strategy/signals.py`, `tests/strategy/*`
- Modify: —

## TDD — Tests First
1. `test_signals.py`: chuỗi giá dựng sẵn → cross long/short đúng vị trí; **no look-ahead**: tín hiệu tại bar t chỉ dùng dữ liệu ≤ close của t, vào lệnh ở open t+1.
2. `test_filters.py`: mỗi filter bật/tắt cho kết quả đúng trên fixture; tổ hợp filter AND đúng.
3. `test_blackout.py`: weekend UTC chặn entry; ts trong/ngoài news window đúng; `cancel_due` true đúng tại news−30' (±1 bar).
4. `test_ema_cross_strategy.py` (integration nhẹ với BacktestEngine tối thiểu): 0 entry vào cuối tuần / trong news window ±30'; entry là market tại open t+1; SL/TP đặt theo ATR. (Cancel-limit chỉ unit-test ở test 3, không assert ở đây.)

## Implementation Steps
1. Viết tests (đỏ).
2. `signals.py` (cross + ghép filter, shift t+1) → pass test 1.
3. `filters.py` → pass test 2.
4. `blackout.py` → pass test 3.
5. `ema_cross.py` (Nautilus Strategy: on_bar gọi signals, áp blackout, đặt/cancel lệnh) → pass test 4.

## Success Criteria
- [ ] Tests phase 2 xanh.
- [ ] No look-ahead được test khẳng định (shift dữ liệu không lộ tương lai).
- [ ] 0 entry vào cuối tuần và trong news window ±30' trên fixture.
- [ ] `cancel_due` đúng mốc news−30' (unit-test; logic cho live).
- [ ] SL/TP theo ATR đặt đúng; SL ban đầu được lưu cho Phase 4.

## Risk Assessment
- Định nghĩa cross mơ hồ (chạm vs vượt) → cố định quy ước, ghi comment.
- Look-ahead ẩn trong cách tính indicator → test shift là chốt chặn.
- API Strategy nautilus_trader (on_bar, submit/cancel order) cần xác minh phiên bản khi cook.
