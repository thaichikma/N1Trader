---
phase: 4
title: "Position Records & Classification"
status: pending
priority: P1
effort: ""
dependencies: [2, 3]
---

# Phase 4: Position Records & Classification

## Overview
Trích kết quả backtest (P3) thành position records chuẩn hoá, tính MAE/MFE/R, và gắn nhãn phân loại 4 chiều (setup/filter · regime · kết quả+MAE/MFE · thời gian). Đây là nguồn sự thật cho dashboard.

## Requirements
- Functional:
<!-- Updated: Validation Session 1 - R = pnl_net / risk(entry→initial_SL); cần lưu initial_sl -->
  - Từ fills/orders/positions của Nautilus → DataFrame chuẩn: `entry_time, exit_time, side, entry_price, exit_price, initial_sl, size, pnl_gross, fees, pnl_net, R, MAE, MFE, bars_held`.
  - **R = pnl_net / |entry_price − initial_sl| × size** (rủi ro ban đầu, Validation #4). Win = `pnl_net > 0`.
  - MAE/MFE: dùng giá 1m trong khoảng giữ lệnh (cần truy cập data 1m P1).
  - Nhãn:
    - `filter_set`: tổ hợp filter bật khi vào lệnh.
    - `regime`: trend↑/trend↓/sideway × vol cao/thấp (ngưỡng ADX/ATR tham số hoá).
    - `outcome`: win/loss, `r_bucket`.
    - `session` (Á/Âu/Mỹ), `weekday`, `near_news` (kể cả khi không bị cấm).
  - Lưu position records ra parquet để dashboard đọc.
- Non-functional: tagger thuần, không phụ thuộc engine; tái lập được từ records + data 1m.

## Architecture
```
n1trader/analysis/
  positions.py  — Nautilus result -> position records (DataFrame chuẩn)
  mae_mfe.py    — tính MAE/MFE/R từ data 1m trong khoảng giữ lệnh
  regime.py     — gán regime theo ADX/ATR (ngưỡng config)
  tagger.py     — ghép tất cả nhãn 4 chiều vào records
```

## Related Code Files
- Create: `n1trader/analysis/positions.py`, `n1trader/analysis/mae_mfe.py`, `n1trader/analysis/regime.py`, `n1trader/analysis/tagger.py`, `tests/analysis/*`
- Modify: —

## TDD — Tests First
1. `test_positions.py`: result Nautilus giả lập → records đúng cột, `pnl_net = pnl_gross − fees`, side/giá khớp.
2. `test_mae_mfe.py`: vị thế biết trước trên chuỗi 1m dựng sẵn → MAE/MFE đúng; R = pnl_net/risk(entry→initial_sl) đúng cho cả long lẫn short.
3. `test_regime.py`: chuỗi trend rõ → gán trend đúng; sideway → sideway; ngưỡng vol đúng.
4. `test_tagger.py`: records → đủ 6 nhãn; `session`/`weekday` đúng theo UTC; `near_news` đúng.

## Implementation Steps
1. Viết tests (đỏ).
2. `positions.py` → pass test 1.
3. `mae_mfe.py` → pass test 2.
4. `regime.py` → pass test 3.
5. `tagger.py` (ghép nhãn) → pass test 4; ghi parquet records.

## Success Criteria
- [ ] Tests phase 4 xanh.
- [ ] `pnl_net` đối soát khớp account report của Nautilus (P3).
- [ ] MAE/MFE/R đúng cho long & short.
- [ ] Records có đủ nhãn 4 chiều, lưu parquet.

## Risk Assessment
- MAE/MFE tốn tính toán (quét 1m mỗi lệnh) → vector hoá theo khoảng, hoặc precompute.
- Định nghĩa regime chủ quan → tham số hoá ngưỡng, ghi rõ; không hard-code.
- Lệch khớp pnl giữa records tự trích và Nautilus → test đối soát là chốt chặn.
