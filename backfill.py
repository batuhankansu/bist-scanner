import sys
sys.path.insert(0, ".")

from scanner import run_backfill


if __name__ == "__main__":
    def print_progress(current, total):
        print(f"  Progress: {current}/{total}")

    result = run_backfill(progress_callback=print_progress)

    if result:
        print(f"\n{'='*50}")
        print(f"  Backfill complete!")
        print(f"  Symbols processed: {result['symbols']}")
        print(f"  Total signals: {result['total']}")
        print(f"    BUY:  {result['buy']}")
        print(f"    SELL: {result['sell']}")
        print(f"{'='*50}")
    else:
        print("No data to backfill.")
