import pandas as pd
from datetime import date, datetime, timezone, timedelta

from config import MIN_BARS
from database import init_db, get_conn, load_ohlcv, insert_signal, get_today_signals, get_previous_signals, set_scan_time
from data_fetcher import get_stock_list, update_data
from indicators import compute_indicators
from strategy import detect_signal, detect_all_signals
from display import print_today_signals, print_previous_signals, print_summary

BIST_TZ = timezone(timedelta(hours=3))
MARKET_CLOSE_HOUR = 18


def is_market_closed() -> bool:
    now = datetime.now(BIST_TZ)
    if now.weekday() >= 5:
        return True
    return now.hour >= MARKET_CLOSE_HOUR


def has_signals() -> bool:
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) FROM signals").fetchone()
    conn.close()
    return row[0] > 0


def run_backfill(progress_callback=None):
    init_db()

    conn = get_conn()
    symbols = [r[0] for r in conn.execute(
        "SELECT DISTINCT symbol FROM ohlcv ORDER BY symbol"
    ).fetchall()]
    conn.close()

    if not symbols:
        return

    total_signals = 0
    buy_count = 0
    sell_count = 0

    for i, symbol in enumerate(symbols):
        if progress_callback and ((i + 1) % 100 == 0 or i == 0):
            progress_callback(i + 1, len(symbols))

        rows = load_ohlcv(symbol, limit=500)
        if len(rows) < MIN_BARS:
            continue

        df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])

        try:
            df = compute_indicators(df)
            signals = detect_all_signals(df)
        except Exception:
            continue

        if signals:
            for sig_date, sig_type, sig_close in signals:
                insert_signal(symbol, sig_date, sig_type, sig_close)
                total_signals += 1
                if sig_type == "BUY":
                    buy_count += 1
                else:
                    sell_count += 1

    return {
        "total": total_signals,
        "buy": buy_count,
        "sell": sell_count,
        "symbols": len(symbols),
    }


def run_scan():
    today_str = date.today().strftime("%Y-%m-%d")
    market_closed = is_market_closed()

    print("Initializing database...")
    init_db()

    if not has_signals():
        print("No signals found. Running backfill first...")
        run_backfill()

    print("Fetching BIST stock list...")
    symbols = get_stock_list()
    if not symbols:
        print("ERROR: Could not fetch stock list. Check your internet connection.")
        return

    print(f"Found {len(symbols)} symbols.")
    update_data(symbols)

    print("Scanning for signals...")
    today_count = 0
    scanned = 0
    errors = 0

    for i, symbol in enumerate(symbols):
        if (i + 1) % 50 == 0 or i == 0:
            print(f"  Progress: {i + 1}/{len(symbols)}")

        rows = load_ohlcv(symbol, limit=100)
        if len(rows) < MIN_BARS:
            errors += 1
            continue

        df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])

        try:
            df = compute_indicators(df)
            result = detect_signal(df, today=today_str if not market_closed else None)

            if result:
                signal_type, close_price = result
                insert_signal(symbol, today_str, signal_type, close_price)
                today_count += 1

            scanned += 1
        except Exception:
            errors += 1
            continue

    today_signals = get_today_signals(today_str)
    previous_signals = get_previous_signals(today_str)

    set_scan_time()

    print_today_signals(today_signals, today_str)
    print_previous_signals(previous_signals)
    print_summary(scanned, today_count, len(today_signals) + len(previous_signals))
