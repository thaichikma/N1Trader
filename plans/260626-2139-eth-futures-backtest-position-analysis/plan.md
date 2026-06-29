---
title: "ETH Futures Backtest & Position Analysis (nautilus_trader)"
description: "Hệ thống Python backtest + phân tích vị thế ETH Futures (Binance) trên nautilus_trader: data 1m, EMA Cross + filters, luật blackout, phí, phân loại vị thế 4 chiều, walk-forward search, dashboard Streamlit. TDD."
status: pending
priority: P2
branch: ""
tags: [backtest, trading, nautilus-trader, eth-futures, streamlit, tdd]
blockedBy: []
blocks: []
created: "2026-06-26T14:50:57.519Z"
createdBy: "ck:plan"
source: skill
---

# ETH Futures Backtest & Position Analysis (nautilus_trader)

## Overview

Xây dựng hệ thống Python để tìm kiếm + phân tích chiến lược giao dịch ETH Futures (Binance) qua backtest dữ liệu 1m (2025→nay). Engine event-driven **nautilus_trader**. Chiến lược #1 = EMA Cross + filters. 3 luật blackout (cuối tuần UTC, news, cancel-limit-30'), phí Binance, position records chuẩn hoá, phân loại vị thế 4 chiều, walk-forward (IS/OOS chống overfit), dashboard Streamlit 4 trang.

**Nguồn:** `plans/reports/brainstorm-260626-2139-eth-futures-backtest-position-analysis-report.md`
**Phương pháp:** TDD — mỗi phase viết test trước, đỏ→xanh→refactor. Trọng tâm test: đúng đắn tài chính (phí, no look-ahead, blackout, MAE/MFE).

## Acceptance Criteria (toàn dự án)

1. Tải đủ OHLCV 1m ETHUSDT Perp từ 2025-01 → nay, lưu local, vá gap, có kiểm tra tính liên tục.
2. Backtest EMA Cross + filters chạy trên nautilus_trader với phí maker/taker Binance.
3. 3 luật blackout hoạt động và có test: weekend UTC, news window, cancel limit 30' trước news.
4. Không look-ahead bias: entry tại open nến kế tiếp sau khi nến tín hiệu đóng — có test khẳng định.
5. Position records chuẩn hoá + nhãn 4 chiều (filter/setup · regime · kết quả+MAE/MFE · thời gian).
6. Walk-forward sinh báo cáo IS vs OOS.
7. Dashboard Streamlit 4 trang: overview, trades+filter, classification, compare.

## Phases

| Phase | Name | Status |
|-------|------|--------|
| 1 | [Scaffold & Data Pipeline](./phase-01-scaffold-data-pipeline.md) | Pending |
| 2 | [Strategy & Blackout Rules](./phase-02-strategy-blackout-rules.md) | Pending |
| 3 | [Engine Config & Fees](./phase-03-engine-config-fees.md) | Pending |
| 4 | [Position Records & Classification](./phase-04-position-records-classification.md) | Pending |
| 5 | [Walk-Forward Search](./phase-05-walk-forward-search.md) | Pending |
| 6 | [Streamlit Dashboard](./phase-06-streamlit-dashboard.md) | Pending |

## Dependencies

```
P1 (data) ──┬─> P2 (strategy+blackout) ──┐
            └─> P3 (engine+fees) ─────────┴─> P4 (positions+classify) ─> P5 (walk-forward)
                                                          └──────────────┴─> P6 (dashboard)
```

- P2, P3 phụ thuộc P1.
- P4 phụ thuộc P2 + P3 (cần backtest chạy ra kết quả để trích position).
- P5 phụ thuộc P4 (search dựa trên metric từ position records).
- P6 phụ thuộc P4 (+ P5 để trang compare IS/OOS).
- Cross-plan: none (greenfield, không plan nào khác).

## Tech Stack

- Python 3.11+, `nautilus_trader`, `pandas`/`polars`, `pyarrow` (parquet), `ccxt` (gap-fill), `requests` (bulk binance.vision), `streamlit` + `plotly`, `pytest`.

## Stale-data / nguồn dữ liệu cần người dùng cung cấp

- **Bảng datetime news** (CSV) cho luật 4/5. Plan giả định người dùng cung cấp file; Phase 1 định nghĩa schema.

## Open Questions — ĐÃ CHỐT (Validation Session 1)

1. **News blackout window:** ±30 phút quanh mốc tin (cấm mở lệnh). Cancel-limit 30' trước giữ nguyên.
2. **Grid tham số:** EMA fast {9,12,21}, slow {26,50,100,200}; filters ADX>{20,25} + ATR-regime.
3. **Entry + SL/TP:** Market tại open t+1; SL ~1.5×ATR, TP ~2-3×ATR (hệ số tham số hoá).
4. **Win/R:** R = pnl_net / (entry→SL ban đầu); win = pnl_net > 0.
5. **Nguồn news:** CSV thủ công do người dùng cung cấp (`datetime_utc, impact, label`).

## Validation Log

### Session 1 — 2026-06-26
- **Verification pass:** Greenfield — toàn bộ file là tạo mới, không có code cũ để grep. Claim ngoài repo (nautilus_trader API, Binance fee/spec) đã đánh dấu "verify khi cook". Failed: 0.
- **Quyết định chốt:** 5 open questions ở trên (tất cả theo Recommended).
- **Hệ quả quan trọng (reconcile):** Chọn **Market entry** → trong backtest KHÔNG có limit order pending → **luật cancel-limit 30' (rule #5) không được kích hoạt trong backtest**. Quyết định: vẫn implement `blackout.cancel_due()` + logic cancel (cho live tương lai), nhưng ở Phase 2 nó được kiểm thử bằng **unit test trên hàm `cancel_due`**, KHÔNG phải assertion mức engine "limit bị cancel". Entry-blackout (weekend + ±30' news) vẫn enforce mức engine và là trọng tâm test.
- **SL/TP theo ATR:** thêm yêu cầu tính ATR trong strategy (Phase 2) và dùng lại cho regime/SL.

### Whole-Plan Consistency Sweep — Session 1
- Phase 2: cập nhật entry=market+ATR SL/TP, news window ±30', làm rõ cancel-limit chỉ unit-test. ✅
- Phase 4: R = pnl_net/risk(entry→SL); cần SL ban đầu trong record. ✅
- Phase 5: grid cố định theo chốt #2. ✅
- Không còn mâu thuẫn chưa giải quyết.
