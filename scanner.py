import pandas as pd
from datetime import date

from config import MIN_BARS
from database import init_db, load_ohlcv, insert_signal, get_today_signals, get_previous_signals
from data_fetcher import get_stock_list, update_data
from indicators import compute_indicators
from strategy import detect_signal
from display import print_today_signals, print_previous_signals, print_summary


def run_scan():
    today_str = date.today().strftime("%Y-%m-%d")

    print("Initializing database...")
    init_db()

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
            result = detect_signal(df)

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

    print_today_signals(today_signals, today_str)
    print_previous_signals(previous_signals)
    print_summary(scanned, today_count, len(today_signals) + len(previous_signals))
