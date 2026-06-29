---
phase: 3
title: "Engine Config & Fees"
status: pending
priority: P1
effort: ""
dependencies: [1]
---

# Phase 3: Engine Config & Fees

## Overview
Cấu hình Nautilus BacktestEngine/BacktestNode: venue Binance Futures, instrument ETHUSDT Perp (precision price/size), phí maker/taker, fill model. Tạo runner sinh kết quả backtest.

## Requirements
- Functional:
  - Khai báo venue Futures + instrument với đúng price/size precision, tick/step size.
  - Phí maker/taker theo Binance Futures (tham số hoá; mặc định taker 0.04% / maker 0.02% — xác nhận khi cook).
  - Fill model hợp lý cho bar data (vào lệnh tại open nến kế tiếp, khớp limit theo high/low nến).
  - `runner.py`: nhận catalog (P1) + strategy config (P2) → chạy → trả account report + fills + orders.
- Non-functional: cấu hình tách khỏi logic chiến lược; phí đổi được không sửa strategy.

## Architecture
```
n1trader/engine/
  venue.py   — BINANCE futures venue, account (margin), instrument ETHUSDT-PERP
  fees.py    — fee model maker/taker (+ optional funding, mặc định tắt V1)
  runner.py  — build BacktestNode config, nạp data, gắn strategy, run, thu kết quả
```

## Related Code Files
- Create: `n1trader/engine/venue.py`, `n1trader/engine/fees.py`, `n1trader/engine/runner.py`, `tests/engine/*`
- Modify: —

## TDD — Tests First
1. `test_fees.py`: 1 fill khối lượng/giá biết trước → phí maker và taker tính đúng theo công thức.
2. `test_venue_instrument.py`: instrument có đúng precision/tick/step; lệnh sai bước bị từ chối/làm tròn đúng quy ước.
3. `test_runner_smoke.py`: chạy backtest trên fixture nhỏ (P1) với strategy mua-giữ-bán đơn giản → account report có phí > 0, số fill khớp kỳ vọng, không lỗi.

## Implementation Steps
1. Viết tests (đỏ).
2. `fees.py` → pass test 1.
3. `venue.py` (venue + instrument spec) → pass test 2.
4. `runner.py` (BacktestNode config + run) → pass test 3.
5. Đối chiếu phí mẫu thủ công với 1-2 lệnh để chốt công thức.

## Success Criteria
- [ ] Tests phase 3 xanh.
- [ ] Backtest smoke chạy ra account report có phí áp dụng đúng.
- [ ] Instrument spec khớp ETHUSDT Perp (precision/tick/step).
- [ ] Phí đổi qua config không cần sửa strategy.

## Risk Assessment
- Sai precision/tick → lệnh bị từ chối hoặc PnL lệch → lấy spec thật từ Binance, test chốt.
- Fill model cho limit trên bar data dễ lạc quan (khớp giá không thực tế) → quy ước bảo thủ (khớp tại giá limit chỉ khi high/low chạm), ghi rõ giả định.
- API BacktestNode/Engine theo phiên bản nautilus_trader → xác minh khi cook.
