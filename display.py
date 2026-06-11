from datetime import date


def print_header(title: str):
    width = 60
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def print_today_signals(signals: list[tuple], today: str):
    print_header(f"TODAY'S SIGNALS — {today}")
    if not signals:
        print("  No signals generated today.")
        print()
        return

    print(f"  {'Symbol':<12} {'Signal':<8} {'Close':>10}")
    print("  " + "-" * 32)
    for symbol, signal_type, close_price in signals:
        marker = "BUY" if signal_type == "BUY" else "SELL"
        print(f"  {symbol:<12} {marker:<8} {close_price:>10.2f}")
    print()


def print_previous_signals(signals: list[tuple]):
    print_header("LATEST SIGNALS (if not today)")
    if not signals:
        print("  No previous signals tracked.")
        print()
        return

    print(f"  {'Symbol':<12} {'Signal':<8} {'Date':<12} {'Close':>10}")
    print("  " + "-" * 44)
    for symbol, signal_date, signal_type, close_price in signals:
        print(f"  {symbol:<12} {signal_type:<8} {signal_date:<12} {close_price:>10.2f}")
    print()


def print_summary(scanned: int, today_count: int, tracked: int):
    print("-" * 60)
    print(f"  Scanned: {scanned} | Today: {today_count} | Tracked: {tracked}")
    print()
