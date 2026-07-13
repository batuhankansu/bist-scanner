"""
Hibrit OHLCV veri cekme modulu.

- Gunluk (1D): yfinance batch download (cok hizli, gecikme onemli degil)
- Intraday (1h/2h/4h): TradingView WebSocket (anlik gercek zamanli veri)

776 BIST sembolu icin:
  1D  → ~3 saniye (yfinance batch)
  1h  → ~120 saniye (TradingView, 4 paralel baglanti x 20 sembol)
"""

import json
import random
import string
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import pandas as pd
import websocket
import yfinance as yf

from config import BIST_TZ, YFINANCE_BATCH_SIZE

MAX_TV_WORKERS = 4
TV_BATCH_SIZE = 20
TV_RECV_TIMEOUT = 20

TV_WS_URL = "wss://data.tradingview.com/socket.io/websocket"
UNAUTH_TOKEN = "unauthorized_user_token"

YF_HISTORY_MAP = {
    "1D": "6mo",
    "240": "3mo",
    "120": "3mo",
    "60": "3mo",
}
YF_INTERVAL_MAP = {
    "1D": "1d",
    "240": "4h",
    "120": "1h",
    "60": "1h",
}


def _rand_id(prefix: str, length: int = 12) -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=length))
    return f"{prefix}_{suffix}"


def _frame(payload: str) -> str:
    return f"~m~{len(payload)}~m~{payload}"


def _parse_frames(raw: str) -> list[dict]:
    messages = []
    i = 0
    while i < len(raw):
        p = raw.find("~m~", i)
        if p == -1:
            break
        p2 = raw.find("~m~", p + 3)
        if p2 == -1:
            break
        try:
            length = int(raw[p + 3 : p2])
        except ValueError:
            i = p2 + 3
            continue
        payload = raw[p2 + 3 : p2 + 3 + length]
        i = p2 + 3 + length
        if payload.startswith("Q~") or payload.startswith("~h~"):
            continue
        try:
            messages.append(json.loads(payload))
        except json.JSONDecodeError:
            continue
    return messages


def _ts_to_date(ts: float) -> str:
    dt = datetime.fromtimestamp(ts, tz=BIST_TZ)
    return dt.strftime("%Y-%m-%d")


def fetch_candles_from_tv(
    symbols: list[str],
    interval: str = "1D",
    count: int = 100,
    progress_callback=None,
) -> dict[str, pd.DataFrame]:
    """
    Hibrit veri cekimi:
    - 1D icin yfinance batch download (hizli)
    - Intraday icin TradingView WebSocket (anlik)
    """
    if interval == "1D":
        return _fetch_daily_yfinance(symbols, count, progress_callback)
    else:
        return _fetch_intraday_tv(symbols, interval, count, progress_callback)


def _fetch_daily_yfinance(
    symbols: list[str],
    count: int,
    progress_callback=None,
) -> dict[str, pd.DataFrame]:
    """yfinance batch download ile gunluk veri cekimi (en hizli yontem)."""
    results = {}
    batches = [
        symbols[i : i + YFINANCE_BATCH_SIZE]
        for i in range(0, len(symbols), YFINANCE_BATCH_SIZE)
    ]
    total_batches = len(batches)

    for bi, batch in enumerate(batches):
        if progress_callback:
            progress_callback(bi, total_batches, batch)

        tickers = [f"{s}.IS" for s in batch]
        try:
            data = yf.download(
                tickers,
                period="6mo",
                interval="1d",
                group_by="ticker",
                progress=False,
                threads=True,
            )
            if data.empty:
                continue

            if len(batch) == 1:
                if not data.empty:
                    df = _clean_yf_df(data)
                    if df is not None:
                        results[batch[0]] = df
            else:
                for ticker, symbol in zip(tickers, batch):
                    try:
                        sub = data[ticker].dropna(how="all")
                        if not sub.empty:
                            df = _clean_yf_df(sub)
                            if df is not None:
                                results[symbol] = df
                    except (KeyError, TypeError):
                        continue
        except Exception:
            continue

        if bi < total_batches - 1:
            time.sleep(0.3)

    if progress_callback:
        progress_callback(total_batches, total_batches, [])

    return results


def _fetch_intraday_tv(
    symbols: list[str],
    interval: str,
    count: int,
    progress_callback=None,
) -> dict[str, pd.DataFrame]:
    """
    TradingView WebSocket ile anlik intraday veri cekimi.
    Sembolleri TV_BATCH_SIZE'lik gruplara boler, paralel baglantilarla ceker.
    """
    results = {}
    batches = [
        symbols[i : i + TV_BATCH_SIZE]
        for i in range(0, len(symbols), TV_BATCH_SIZE)
    ]
    total_batches = len(batches)

    if progress_callback:
        progress_callback(0, total_batches, [])

    with ThreadPoolExecutor(max_workers=MAX_TV_WORKERS) as executor:
        futures = {
            executor.submit(_tv_fetch_batch, batch, interval, count): bi
            for bi, batch in enumerate(batches)
        }
        for future in as_completed(futures):
            bi = futures[future]
            try:
                batch_result = future.result()
                results.update(batch_result)
                if progress_callback:
                    progress_callback(bi + 1, total_batches, batches[bi])
            except Exception:
                continue

    if progress_callback:
        progress_callback(total_batches, total_batches, [])

    return results


def _tv_fetch_batch(
    symbols: list[str],
    interval: str,
    count: int,
) -> dict[str, pd.DataFrame]:
    """Tek WebSocket baglantisiyla birden fazla sembolun anlik verisini ceker."""
    chart_sessions = {}
    received = {}
    completed = {}
    done_event = threading.Event()

    for sym in symbols:
        chart_sessions[sym] = _rand_id("cs")

    def on_message(ws, message):
        for msg in _parse_frames(message):
            m = msg.get("m")
            if m in ("du", "timescale_update"):
                try:
                    p = msg.get("p", [])
                    if len(p) < 2:
                        continue
                    cs = p[0]
                    data = p[1]
                    if not isinstance(data, dict):
                        continue
                    sym = None
                    for s, s_cs in chart_sessions.items():
                        if s_cs == cs:
                            sym = s
                            break
                    if not sym:
                        continue
                    for val in data.values():
                        if isinstance(val, dict) and "s" in val:
                            bars = []
                            for bar in val["s"]:
                                v = bar.get("v", [])
                                if len(v) >= 6:
                                    bars.append(
                                        {
                                            "date": v[0],
                                            "open": float(v[1]),
                                            "high": float(v[2]),
                                            "low": float(v[3]),
                                            "close": float(v[4]),
                                            "volume": int(v[5]),
                                        }
                                    )
                            if bars:
                                if sym not in received:
                                    received[sym] = []
                                existing = {b["date"] for b in received[sym]}
                                for b in bars:
                                    if b["date"] not in existing:
                                        received[sym].append(b)
                                        existing.add(b["date"])
                except Exception:
                    pass

            elif m == "series_completed":
                try:
                    p = msg.get("p", [])
                    cs = p[0] if p else None
                    for s, s_cs in chart_sessions.items():
                        if s_cs == cs:
                            completed[s] = True
                            break
                    if len(completed) >= len(symbols):
                        done_event.set()
                except Exception:
                    pass

            elif m == "symbol_error":
                try:
                    p = msg.get("p", [])
                    cs = p[0] if p else None
                    for s, s_cs in chart_sessions.items():
                        if s_cs == cs:
                            completed[s] = True
                            break
                    if len(completed) >= len(symbols):
                        done_event.set()
                except Exception:
                    pass

    def on_error(ws, error):
        done_event.set()

    def on_close(ws, code, msg):
        done_event.set()

    def on_open(ws):
        try:
            ws.send(_frame(json.dumps({"m": "set_auth_token", "p": [UNAUTH_TOKEN]})))
            for sym, cs in chart_sessions.items():
                ws.send(
                    _frame(
                        json.dumps({"m": "chart_create_session", "p": [cs, ""]})
                    )
                )
            for i, (sym, cs) in enumerate(chart_sessions.items()):
                alias = f"sds_sym_{i + 1}"
                desc = json.dumps(
                    {
                        "symbol": f"BIST:{sym}",
                        "adjustment": "splits",
                        "session": "regular",
                    }
                )
                ws.send(
                    _frame(
                        json.dumps(
                            {
                                "m": "resolve_symbol",
                                "p": [cs, alias, f"={desc}"],
                            }
                        )
                    )
                )
                ws.send(
                    _frame(
                        json.dumps(
                            {
                                "m": "create_series",
                                "p": [cs, "sds_1", "s1", alias, interval, count],
                            }
                        )
                    )
                )
        except Exception:
            done_event.set()

    ws = websocket.WebSocketApp(
        TV_WS_URL,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open,
    )

    ws_thread = threading.Thread(
        target=lambda: ws.run_forever(ping_interval=15, ping_timeout=10),
        daemon=True,
    )
    ws_thread.start()
    done_event.wait(timeout=TV_RECV_TIMEOUT)

    try:
        ws.close()
    except Exception:
        pass

    results = {}
    for sym, bars in received.items():
        if bars:
            df = pd.DataFrame(bars)
            df["date"] = df["date"].apply(_ts_to_date)
            df = df.drop_duplicates(subset="date", keep="last")
            df = df.sort_values("date").reset_index(drop=True)
            if len(df) >= 1:
                results[sym] = df

    return results


def _clean_yf_df(df: pd.DataFrame) -> pd.DataFrame | None:
    """yfinance DataFrame'ini temizle."""
    try:
        if df.empty:
            return None
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
        if not rows:
            return None
        df_out = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
        df_out = df_out.drop_duplicates(subset="date", keep="last")
        df_out = df_out.sort_values("date").reset_index(drop=True)
        return df_out
    except Exception:
        return None


def fetch_candles_with_db_fallback(
    symbols: list[str],
    use_db: bool = True,
    interval: str = "1D",
    count: int = 100,
    progress_callback=None,
) -> dict[str, pd.DataFrame]:
    """Veri ceker, basarisizsa veritabanindan yukler."""
    results = fetch_candles_from_tv(symbols, interval, count, progress_callback)

    if use_db:
        from database import load_ohlcv

        missing = [s for s in symbols if s not in results]
        if missing and progress_callback:
            progress_callback(-1, -1, missing)
        for sym in missing:
            rows = load_ohlcv(sym, limit=count)
            if len(rows) >= 50:
                df = pd.DataFrame(
                    rows, columns=["date", "open", "high", "low", "close", "volume"]
                )
                results[sym] = df

    return results


def fetch_realtime_quote(symbols: list[str]) -> dict[str, dict]:
    """Anlik fiyatlari yfinance ile ceker."""
    results = {}

    def fetch_one(sym):
        try:
            ticker = yf.Ticker(f"{sym}.IS")
            info = ticker.fast_info
            price = getattr(info, "last_price", None)
            prev = getattr(info, "previous_close", None)
            vol = getattr(info, "last_volume", 0) or 0
            chg = 0.0
            if price and prev and prev > 0:
                chg = (price - prev) / prev * 100
            if price:
                return sym, {
                    "price": float(price),
                    "volume": int(vol),
                    "change_pct": round(chg, 2),
                }
        except Exception:
            pass
        return sym, None

    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = {executor.submit(fetch_one, s): s for s in symbols}
        for future in as_completed(futures):
            try:
                sym, data = future.result()
                if data:
                    results[sym] = data
            except Exception:
                continue

    return results
