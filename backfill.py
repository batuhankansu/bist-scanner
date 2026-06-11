import sys
sys.path.insert(0, ".")

import pandas as pd
from database import init_db, get_conn, load_ohlcv, insert_signal
from indicators import compute_indicators
from strategy import detect_all_signals
from config import MIN_BARS


def backfill():
    init_db()

    conn = get_conn()
    symbols = [r[0] for r in conn.execute(
        "SELECT DISTINCT symbol FROM ohlcv ORDER BY symbol"
    ).fetchall()]
    conn.close()

    print(f"Backfilling historical signals for {len(symbols)} symbols...\n")

    total_signals = 0
    symbols_with_signals = 0
    buy_count = 0
    sell_count = 0

    for i, symbol in enumerate(symbols):
        if (i + 1) % 100 == 0:
            print(f"  Progress: {i + 1}/{len(symbols)}")

        rows = load_ohlcv(symbol, limit=500)
        if len(rows) < MIN_BARS:
            continue

        df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])

        try:
            df = compute_indicators(df)
            signals = detect_all_signals(df)
        except Exception as e:
            continue

        if signals:
            symbols_with_signals += 1
            for sig_date, sig_type, sig_close in signals:
                insert_signal(symbol, sig_date, sig_type, sig_close)
                total_signals += 1
                if sig_type == "BUY":
                    buy_count += 1
                else:
                    sell_count += 1

    print(f"\n{'='*50}")
    print(f"  Backfill complete!")
    print(f"  Symbols processed: {len(symbols)}")
    print(f"  Symbols with signals: {symbols_with_signals}")
    print(f"  Total signals: {total_signals}")
    print(f"    BUY:  {buy_count}")
    print(f"    SELL: {sell_count}")
    print(f"{'='*50}")


if __name__ == "__main__":
    backfill()
