# AGENTS.md — BIST Signal Scanner

## Project Overview

A Python-based daily stock scanner for Borsa Istanbul (BIST). Converts a Pine Script multi-indicator strategy into Python and runs it across all ~776 BIST symbols. Tracks buy/sell signal history in SQLite so you can see which stocks signaled today vs. their latest previous signal.

## Quick Start

```bash
cd C:\Code\bist-scanner
python run.py
```

This launches the Streamlit web dashboard at `http://localhost:8501`.

First run downloads ~6 months of OHLCV data for all symbols (2-3 min). Subsequent runs only fetch new daily bars (15-30 sec). You can also trigger a scan from the dashboard's sidebar "Run Scan" button.

## File Structure

```
bist-scanner/
├── run.py              # Entry point — launches Streamlit app
├── app.py              # Streamlit dashboard (main UI)
├── backfill.py         # One-off script to backfill historical signals
├── ui/
│   ├── __init__.py
│   ├── cache.py        # @st.cache_data wrappers for DB queries + indicator computation
│   └── tables.py       # Signal table rendering with st.dataframe
├── config.py           # All strategy parameters (EMA, MACD, RSI, ADX, paths)
├── database.py         # SQLite: OHLCV cache + signal history
├── data_fetcher.py     # Stock list via borsapy, OHLCV via yfinance bulk download
├── indicators.py       # EMA, MACD, RSI, DMI/ADX via `ta` library
├── strategy.py         # Buy/sell signal logic + detect_all_signals() for history
├── scanner.py          # Main scan loop: update data → compute → detect → store
├── display.py          # Terminal table formatting (CLI fallback)
├── bist.db             # SQLite database (auto-created on first run)
└── requirements.txt    # yfinance, borsapy, ta, pandas, streamlit, plotly
```

## Dependencies

- Python 3.12 (installed via winget)
- `yfinance` — bulk OHLCV download with `.IS` suffix for BIST
- `borsapy` — BIST stock list (`bp.companies()` returns DataFrame with `ticker` column)
- `ta` — pure Python technical indicators (no C compilation needed)
- `pandas` — data manipulation
- `streamlit` — web dashboard framework
- `plotly` — interactive candlestick charts

All installed at: `C:\Users\PC\AppData\Local\Programs\Python\Python312\Lib\site-packages`

## Web Dashboard (Streamlit)

Launch: `python run.py` or `streamlit run app.py`

### Layout

- **Sidebar**: Run Scan button + strategy parameter sliders (EMA, MACD, RSI, ADX)
- **Tab 1 — Today's Signals**: Color-coded BUY/SELL table for current day
- **Tab 2 — Signal History**: Full history with date range, type filter, symbol search
- **Tab 3 — Charts**: Candlestick chart with EMA overlays + MACD/RSI/ADX subplots

### Caching

- `ui/cache.py` uses `@st.cache_data` for DB queries (1 hour TTL) and chart computation (5 min TTL)
- Changing strategy sliders invalidates chart cache for affected symbols
- "Run Scan" button clears all caches and refreshes the page

### Charts

4-row Plotly subplots:
1. Candlestick + EMA(fast) + EMA(slow)
2. MACD line + Signal line + Histogram
3. RSI + threshold lines (buy/sell levels)
4. ADX + +DI/-DI + minimum ADX line

## Data Flow

1. `borsapy.companies()` → DataFrame with ~776 BIST tickers
2. `yfinance.download()` → batch download OHLCV in groups of 50, `.IS` suffix
3. Store in SQLite (`ohlcv` table) keyed by `(symbol, date)`
4. On subsequent runs, check `get_last_date(symbol)` — only download if stale
5. Load last 100 bars from DB per symbol, compute indicators, check last bar for signal
6. If signal found, insert into `signals` table
7. Display two tables: today's signals + latest previous signals

## Database Schema (SQLite)

```sql
-- OHLCV cache
CREATE TABLE ohlcv (
    symbol TEXT, date TEXT,
    open REAL, high REAL, low REAL, close REAL, volume INTEGER,
    PRIMARY KEY (symbol, date)
);

-- Signal history
CREATE TABLE signals (
    symbol TEXT, signal_date TEXT, signal_type TEXT, close_price REAL,
    PRIMARY KEY (symbol, signal_date, signal_type)
);
```

Key functions: `database.py` — `get_last_date()`, `insert_ohlcv()`, `load_ohlcv()`, `insert_signal()`, `get_today_signals()`, `get_previous_signals()`

## Strategy Logic (Pine Script → Python)

Original Pine Script: EMA(7/21) crossover + MACD(10/18/9) + RSI(14) + DMI/ADX(4)

### Buy Signal — ALL conditions must be true:
1. EMA(7) crosses above EMA(21), OR near-cross detected (dist ≤ 0.40% and slope_fast > slope_slow)
2. MACD bullish: MACD crosses above signal, OR (MACD > signal and histogram > 0)
3. RSI > 47.0
4. +DI > -DI and ADX ≥ 20.0

### Sell Signal — ALL conditions must be true:
1. EMA(7) crosses below EMA(21), OR near-cross detected (dist ≤ 0.40% and slope_fast < 0)
2. MACD bearish: MACD crosses below signal, OR (MACD < signal and histogram < 0)
3. RSI < 55.0
4. -DI > +DI and ADX ≥ 20.0

Implementation in `strategy.py:detect_signal()` — returns `(signal_type, close_price)` or `None`.

## Configuration (config.py)

| Parameter | Default | Description |
|-----------|---------|-------------|
| EMA_FAST | 7 | Fast EMA period |
| EMA_SLOW | 21 | Slow EMA period |
| NEAR_CROSS_PCT | 0.40 | Near-cross tolerance (%) |
| MACD_FAST | 10 | MACD fast period |
| MACD_SLOW | 18 | MACD slow period |
| MACD_SIGNAL | 9 | MACD signal period |
| RSI_PERIOD | 14 | RSI period |
| RSI_BUY_LEVEL | 47.0 | RSI threshold for buy |
| RSI_SELL_LEVEL | 55.0 | RSI threshold for sell |
| DMI_PERIOD | 4 | DMI/ADX period |
| ADX_MIN | 20.0 | Minimum ADX for trend strength |
| HISTORY_PERIOD | 6mo | How far back to download OHLCV |
| MIN_BARS | 50 | Minimum bars needed before scanning |
| YFINANCE_BATCH_SIZE | 50 | Symbols per yfinance download batch |
| DB_PATH | bist.db | SQLite database path |

## Data Source Notes

- **borsapy** `companies()` may show a default openpyxl warning — harmless, ignore it
- **yfinance** delists many old/inactive BIST symbols (~169 fail with "possibly delisted") — these are silently skipped
- **yfinance** rate limits: batch download with 0.5s delay between batches; 3 retries with 2s backoff on failure
- **BIST stock list** source chain: borsapy → borsaistanbul.com CSV fallback → empty list
- **Single stock fallback**: `fetch_single()` in data_fetcher.py for retrying failed symbols individually

## Known Gotchas

1. **ADX with small data**: `ta.trend.ADXIndicator` fails with < ~10 bars. MIN_BARS=50 prevents this.
2. **PowerShell quoting**: Multi-line `python -c "..."` breaks on nested quotes. Use script files instead.
3. **PATH refresh**: After Python install, must refresh PATH: `$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")`
4. **yfinance multi-ticker**: When batch has 1 ticker, data comes as flat DataFrame; when >1, it's multi-level with ticker as top column. `fetch_yfinance()` handles both cases.
5. **Near-cross slope logic**: Pine Script checks `slopeFast < 0` for near-cross-down, but `slopeFast > slopeSlow` for near-cross-up. This asymmetry is intentional.
6. **Signal deduplication**: PRIMARY KEY on `(symbol, signal_date, signal_type)` means re-running same day replaces the signal (INSERT OR REPLACE).

## Extending the Project

- **Add new indicators**: Add to `indicators.py`, wire into `strategy.py:detect_signal()`
- **Change output format**: Edit `display.py` (currently prints to stdout)
- **Add Telegram/email alerts**: Hook into `scanner.py` after `insert_signal()` call
- **Adjust strategy params**: Edit `config.py` defaults, no code changes needed
- **Filter symbols**: Modify `get_stock_list()` to return subset (e.g., BIST 100 only)
- **UI modifications**: Edit `app.py` for layout, `ui/cache.py` for caching logic, `ui/tables.py` for table formatting

## Running Tests

No formal test suite. Manual verification:
```bash
# Test single stock pipeline
python -c "from database import init_db; from data_fetcher import fetch_single; from indicators import compute_indicators; from strategy import detect_signal; import pandas as pd; init_db(); fetch_single('THYAO'); rows = __import__('database').load_ohlcv('THYAO'); df = pd.DataFrame(rows, columns=['date','open','high','low','close','volume']); df = compute_indicators(df); print(detect_signal(df))"
```

## Backfilling Historical Signals

The `backfill.py` script scans all historical bars (not just the last bar) for signals:

```bash
python backfill.py
```

This iterates through each bar from index 50 (MIN_BARS) to the end of the data, checking for signals at each point. Results are stored in the `signals` table with the correct historical date.

### How It Works

1. Loads all available OHLCV data per symbol (up to 500 bars)
2. Computes indicators once on the full DataFrame
3. Iterates from bar 50 to end, calling `detect_signal()` on each slice
4. Stores each historical signal via `insert_signal()`

### Chart Signal Markers

The dashboard's Charts tab displays historical signals as markers on the candlestick chart:
- Green triangles (▲) = BUY signals
- Red triangles (▼) = SELL signals
- Hover shows date and price

Signal count is displayed below the metrics bar (e.g., "5 historical signals: 3 BUY, 2 SELL").

## Common Commands

```bash
# Full scan
python run.py

# Check database size
python -c "import os; print(f'{os.path.getsize(\"bist.db\") / 1024 / 1024:.1f} MB')"

# Query today's signals directly
python -c "import sqlite3; conn = sqlite3.connect('bist.db'); print(conn.execute('SELECT * FROM signals WHERE signal_date = date(\"now\")').fetchall())"

# Query all tracked symbols
python -c "import sqlite3; conn = sqlite3.connect('bist.db'); print(conn.execute('SELECT COUNT(DISTINCT symbol) FROM ohlcv').fetchone()[0], 'symbols cached')"
```
