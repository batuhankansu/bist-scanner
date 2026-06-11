import time
import yfinance as yf
import pandas as pd
from datetime import date, timedelta

from config import HISTORY_PERIOD, YFINANCE_BATCH_SIZE, MIN_BARS
from database import get_last_date, insert_ohlcv


def get_stock_list() -> list[str]:
    try:
        import borsapy as bp
        df = bp.companies()
        symbols = df["ticker"].dropna().astype(str).tolist()
        if symbols:
            return sorted(set(symbols))
    except Exception:
        pass

    try:
        df = pd.read_csv("https://www.borsaistanbul.com/datum/hisse_endeks_ds.csv")
        col = [c for c in df.columns if "KOD" in c.upper() or "SYMBOL" in c.upper() or "code" in c.lower()]
        if col:
            return sorted(set(df[col[0]].dropna().astype(str).tolist()))
    except Exception:
        pass

    return []


def fetch_yfinance(symbols: list[str], period: str = HISTORY_PERIOD) -> dict[str, pd.DataFrame]:
    results = {}
    batches = [symbols[i:i + YFINANCE_BATCH_SIZE] for i in range(0, len(symbols), YFINANCE_BATCH_SIZE)]

    for batch_idx, batch in enumerate(batches):
        tickers = [f"{s}.IS" for s in batch]
        for attempt in range(3):
            try:
                data = yf.download(
                    tickers,
                    period=period,
                    interval="1d",
                    group_by="ticker",
                    progress=False,
                    threads=True,
                )
                if data.empty:
                    break

                if len(batch) == 1:
                    ticker = tickers[0]
                    symbol = batch[0]
                    if not data.empty:
                        results[symbol] = data
                else:
                    for ticker, symbol in zip(tickers, batch):
                        try:
                            sub = data[ticker].dropna(how="all")
                            if not sub.empty:
                                results[symbol] = sub
                        except (KeyError, TypeError):
                            continue
                break
            except Exception:
                if attempt < 2:
                    time.sleep(2)
                continue

        if batch_idx < len(batches) - 1:
            time.sleep(0.5)

    return results


def update_data(symbols: list[str], force_today: bool = False) -> int:
    today_str = date.today().strftime("%Y-%m-%d")
    updated = 0

    need_download = []
    for symbol in symbols:
        last = get_last_date(symbol)
        if last is None or (force_today and last == today_str) or (not force_today and last < today_str):
            need_download.append(symbol)

    if not need_download:
        return 0

    print(f"  Downloading data for {len(need_download)} symbols...")
    data = fetch_yfinance(need_download)

    for symbol, df in data.items():
        if df.empty:
            continue
        rows = []
        for idx, row in df.iterrows():
            d = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
            try:
                o = float(row["Open"]) if pd.notna(row["Open"]) else None
                h = float(row["High"]) if pd.notna(row["High"]) else None
                l = float(row["Low"]) if pd.notna(row["Low"]) else None
                c = float(row["Close"]) if pd.notna(row["Close"]) else None
                v = int(row["Volume"]) if pd.notna(row["Volume"]) else 0
                if o and h and l and c and v > 0:
                    rows.append((d, o, h, l, c, v))
            except (ValueError, TypeError):
                continue
        if rows:
            insert_ohlcv(symbol, rows)
            updated += 1

    return updated


def fetch_single(symbol: str) -> pd.DataFrame | None:
    try:
        ticker = yf.Ticker(f"{symbol}.IS")
        df = ticker.history(period=HISTORY_PERIOD, interval="1d")
        if df is not None and not df.empty:
            rows = []
            for idx, row in df.iterrows():
                d = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
                try:
                    o = float(row["Open"])
                    h = float(row["High"])
                    l = float(row["Low"])
                    c = float(row["Close"])
                    v = int(row["Volume"])
                    if v > 0:
                        rows.append((d, o, h, l, c, v))
                except (ValueError, TypeError):
                    continue
            if rows:
                insert_ohlcv(symbol, rows)
            return df
    except Exception:
        pass
    return None
