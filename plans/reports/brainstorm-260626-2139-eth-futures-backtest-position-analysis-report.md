# Brainstorm Report — Hệ thống Backtest & Phân tích Vị thế ETH Futures (N1Trader)

- **Ngày:** 2026-06-26
- **Skill:** /brainstorm
- **Nguồn yêu cầu:** `Mục tiêu dự án.md`
- **Trạng thái repo:** Greenfield (chưa có code/docs/plans)
- **Modes:** none (no --html / --wiki)

---

## 1. Problem Statement & Requirements

Xây dựng hệ thống Python để **tìm kiếm + phân tích chiến lược giao dịch ETH Futures (Binance)** thông qua backtest trên dữ liệu 1 phút, kèm dashboard và hệ thống phân loại vị thế.

### Yêu cầu gốc (từ `Mục tiêu dự án.md`)
1. Tìm kiếm, phân tích chiến lược giao dịch ETH Futures trên Binance.
2. Tải OHLCV 1m từ 2025 → hiện tại để backtest/phân tích.
3. Cấm giao dịch cuối tuần (UTC).
4. Cấm mở lệnh mới trước/sau tin tức tài chính lớn.
5. Cancel toàn bộ limit order chưa khớp **30 phút trước** tin tức.
6. Backtest phải tính **phí giao dịch Binance**.
7. Chiến lược #1: **EMA Cross + filters**.

### Yêu cầu bổ sung (từ phiên brainstorm)
- Dashboard đầy đủ.
- Hệ thống phân loại vị thế.

### Quyết định đã chốt (Discovery Phase)
| Khía cạnh | Quyết định |
|---|---|
| Ngôn ngữ | Python |
| Backtest engine | **nautilus_trader** (event-driven, lõi Rust) |
| Strategy search | Walk-forward + train/test split — nâng cao ngay Vòng 1 |
| Phân loại vị thế | 4 chiều (filter/setup · regime · kết quả+MAE/MFE · thời gian) |
| Dashboard | Streamlit |
| Xử lý news | Bảng datetime do người dùng cung cấp → sinh blackout windows |
| Chiến lược #1 | EMA Cross + filters |

### Định nghĩa "Done" (Acceptance Criteria)
1. Tải đủ OHLCV 1m ETH (Binance Futures) từ 01/2025 → hiện tại, lưu local, vá gap.
2. Chạy backtest EMA Cross + filters trên nautilus_trader với **phí maker/taker Binance**.
3. 3 luật blackout hoạt động: cuối tuần UTC, news blackout, cancel limit 30' trước news.
4. **Không look-ahead bias**: entry tại open nến kế tiếp sau khi nến tín hiệu đóng.
5. Sinh **position records chuẩn hoá** + gắn nhãn 4 chiều.
6. Walk-forward chạy được: báo cáo IS vs OOS để phát hiện overfit.
7. Dashboard Streamlit: overview, bảng vị thế lọc theo 4 nhãn, breakdown phân loại, so sánh tham số.

### Phạm vi
- **Trong scope V1:** data pipeline 1m, Strategy 1 (EMA cross + filters), engine + 3 luật blackout, phí, position records, phân loại 4 chiều, walk-forward search, dashboard 4 trang.
- **Ngoài scope:** live trading thật, đa chiến lược/đa cặp, funding rate chi tiết, Monte-Carlo, tối ưu hyper nâng cao (Optuna/Bayesian) — để vòng sau.

---

## 2. Evaluated Approaches

### Trục 1 — Loại engine
| Hướng | Mô tả | Ưu | Nhược | Kết |
|---|---|---|---|---|
| A. Vectorized (vectorbt) | Signal vector + blackout mask | Cực nhanh, hợp param-sweep, ít code | Order lifecycle yếu | Loại (user chọn event-driven) |
| **B. Event-driven** | Mô phỏng từng sự kiện/lệnh | Limit/cancel chân thực, sát live | Chậm hơn khi sweep | **Chọn** |
| C. Hybrid tùy biến | Engine tự viết | Kiểm soát tuyệt đối | Tốn công, vi phạm KISS | Loại |

### Trục 2 — Library event-driven (sau khi chốt B)
| Library | Tốc độ | Order lifecycle | Binance Futures | Lên live | Kết |
|---|---|---|---|---|---|
| backtrader | 🐢 | ✅ | qua ccxt | Khá | Loại (chậm với walk-forward 1m) |
| backtesting.py | 🚶 | ⚠️ | DIY | Yếu | Loại |
| **nautilus_trader** | 🚀 (Rust) | ✅ Rất tốt | ✅ Native | ✅ Rất tốt | **Chọn** |

**Lý do chốt nautilus_trader:** dữ liệu 1m + walk-forward cần tốc độ; luật 3/4/5 vốn là luật live-trading và có định hướng chạy thật → cùng codebase backtest↔live; mô phỏng limit/cancel chuẩn → luật #5 không phải rút gọn.

---

## 3. Recommended Solution

### Kiến trúc module
```
n1trader/
├── data/                      (1) Data layer
│   ├── downloader.py             — bulk 1m từ data.binance.vision (zip/tháng) + ccxt vá gap
│   ├── catalog.py                — nạp Bar vào Nautilus ParquetDataCatalog
│   └── news_windows.py           — bảng datetime news → sinh blackout windows
├── strategy/                  (2) Strategy layer
│   ├── ema_cross.py              — Nautilus Strategy: tín hiệu EMA fast/slow cross
│   ├── filters.py                — ADX/ATR/volume/EMA-slope... (bật/tắt, cấu hình)
│   └── blackout.py               — weekend(UTC) + news + cancel-limit-30' (trong on_bar)
├── engine/                    (3) Backtest config
│   ├── venue.py                  — Binance Futures venue, instrument + maker/taker fees
│   └── runner.py                 — BacktestNode/Engine config, fill model
├── analysis/                  (4) Classification & analytics
│   ├── positions.py              — extract Nautilus reports → position records chuẩn hoá
│   ├── tagger.py                 — gắn nhãn 4 chiều
│   ├── regime.py                 — trend/sideway × vol (ADX/ATR)
│   └── mae_mfe.py                — MAE/MFE/R-multiple trong lệnh
├── optimize/                  (5) Strategy search
│   └── walk_forward.py           — rolling train/test, grid EMA+filter, rank IS/OOS
└── dashboard/                 (6) Streamlit
    ├── overview.py               — equity, drawdown, KPIs
    ├── trades.py                 — bảng vị thế + filter theo 4 nhãn
    ├── classification.py         — breakdown hiệu suất theo từng chiều
    └── compare.py                — so sánh tham số / IS vs OOS
```

### Position record (nguồn sự thật cho phân loại)
`entry_time, exit_time, side, entry_price, exit_price, size, pnl_gross, fees, pnl_net, R, MAE, MFE, bars_held` + nhãn: `filter_set, regime, session, weekday, near_news, outcome(win/loss)`.

### Phân loại 4 chiều
1. **Setup/filter:** tổ hợp filter đang bật khi vào lệnh → filter nào hiệu quả.
2. **Regime:** trend↑/trend↓/sideway × vol cao/thấp (ngưỡng ADX/ATR tham số hoá).
3. **Kết quả & MAE/MFE:** win/loss, R-bucket, chất lượng entry (MAE thấp = entry tốt).
4. **Thời gian:** phiên Á/Âu/Mỹ, thứ trong tuần, gần news.

### Luật blackout (event-driven, trong `on_bar`)
- **Weekend:** timestamp UTC là Sat/Sun → không mở lệnh mới.
- **News blackout:** entry rơi trong window quanh datetime news → không mở lệnh mới.
- **Cancel limit 30':** trước mỗi news 30 phút → cancel mọi limit order pending (mô phỏng thật nhờ order lifecycle của Nautilus).

### Walk-forward
Rolling/anchored windows: train (chọn tham số tốt nhất theo metric) → test OOS → roll. Báo cáo IS vs OOS để lộ overfit. DIY harness chạy `BacktestNode` theo từng config tham số.

---

## 4. Implementation Considerations & Risks

| # | Rủi ro | Giảm thiểu |
|---|---|---|
| 1 | Tải 1m 2025→nay (~750k+ nến) chậm nếu dùng REST | Dùng bulk `data.binance.vision` (zip theo tháng), ccxt chỉ vá gap gần đây |
| 2 | Look-ahead bias | Entry tại open nến kế tiếp sau khi nến tín hiệu đóng; test khẳng định |
| 3 | Overfitting khi sweep | Walk-forward + báo cáo IS/OOS ngay V1 |
| 4 | "Regime" chủ quan | Tham số hoá ngưỡng ADX/ATR, ghi rõ định nghĩa |
| 5 | Learning curve nautilus_trader dốc | Bắt đầu bằng 1 backtest tối thiểu chạy được trước khi thêm filter/sweep |
| 6 | Phí/đòn bẩy Binance Futures cấu hình sai | Khai báo maker/taker + (tùy chọn) funding trong instrument; đối chiếu tài liệu Binance |
| 7 | Định dạng/độ chính xác giá-khối lượng (price/size precision) | Lấy đúng instrument spec ETHUSDT Perp |

---

## 5. Success Metrics & Validation

- Backtest EMA Cross chạy hết dữ liệu 1m không lỗi, có phí.
- Số liệu equity/drawdown/winrate/PF khớp giữa Nautilus report và position records tự trích.
- 3 luật blackout có test đơn vị (không có entry cuối tuần/trong news window; limit bị cancel đúng mốc 30').
- Test no-look-ahead: dịch tín hiệu 1 nến không đổi kết quả bất thường.
- Walk-forward cho ra bảng IS vs OOS; dashboard lọc được theo cả 4 nhãn.

---

## 6. Next Steps & Dependencies

- **Tiếp theo:** chuyển sang `/ck:plan` để chia phase (đề xuất `--tdd` do tính đúng đắn tài chính: phí, no-look-ahead, blackout).
- **Phụ thuộc dữ liệu cần người dùng cung cấp:** bảng datetime news tài chính (CSV/parquet) cho luật 4/5.
- **Phụ thuộc kỹ thuật:** Python env + nautilus_trader, quyền truy cập data.binance.vision / ccxt, instrument spec ETHUSDT Perpetual.

---

## 7. Unresolved Questions

1. **Khoảng blackout news:** "trước/sau" tin tức là bao nhiêu phút mỗi bên (ngoài luật cancel-limit 30')? Cần con số cụ thể để mã hoá window.
2. **Tham số EMA + filter cụ thể:** dải giá trị fast/slow EMA và danh sách filter chính xác (ADX? ATR? volume? khác?) để định nghĩa grid walk-forward.
3. **Cấu hình lệnh:** entry dạng market hay limit? Đòn bẩy? SL/TP cố định, theo ATR, hay trailing?
4. **Định nghĩa win/loss & R:** dựa trên pnl_net hay R-multiple từ SL ban đầu?
5. **Nguồn bảng news:** người dùng tự nhập hay cần script tải về? (hiện giả định người dùng cung cấp file).
