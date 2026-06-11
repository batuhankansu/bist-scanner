import pandas as pd
import streamlit as st
from datetime import date

from database import get_conn, load_ohlcv
from indicators import compute_indicators, tradingview_dmi_adx
from strategy import detect_signal, detect_all_signals
from scanner import is_market_closed
from config import (
    EMA_FAST, EMA_SLOW, MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    RSI_PERIOD, RSI_BUY_LEVEL, RSI_SELL_LEVEL,
    DMI_PERIOD, ADX_MIN, MIN_BARS, NEAR_CROSS_PCT,
)


@st.cache_data(ttl=3600, show_spinner=False)
def load_signals_df(all_signals: bool = False) -> pd.DataFrame:
    conn = get_conn()
    if all_signals:
        df = pd.read_sql_query(
            "SELECT symbol, signal_date, signal_type, close_price "
            "FROM signals ORDER BY signal_date DESC, symbol",
            conn,
        )
    else:
        today = date.today().strftime("%Y-%m-%d")
        df = pd.read_sql_query(
            "SELECT symbol, signal_type, close_price "
            "FROM signals WHERE signal_date = ? ORDER BY signal_type, symbol",
            conn,
            params=(today,),
        )
    conn.close()
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_symbols_list() -> list[str]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT symbol FROM ohlcv ORDER BY symbol"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


@st.cache_data(ttl=300, show_spinner=False)
def compute_stock_chart(
    symbol: str,
    ema_fast: int,
    ema_slow: int,
    macd_fast: int,
    macd_slow: int,
    macd_signal: int,
    rsi_period: int,
    rsi_buy: float,
    rsi_sell: float,
    dmi_period: int,
    adx_min: float,
    near_cross_pct: float,
):
    import ta
    import plotly.graph_objects as go
    from config import MIN_BARS

    rows = load_ohlcv(symbol, limit=100)
    if len(rows) < MIN_BARS:
        return None

    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = df["date"].apply(lambda d: f"{d[8:10]}/{d[5:7]}/{d[:4]}" if isinstance(d, str) and len(d) >= 10 else d)

    close = df["close"]
    high = df["high"]
    low = df["low"]

    df["ema_fast"] = ta.trend.ema_indicator(close, window=ema_fast)
    df["ema_slow"] = ta.trend.ema_indicator(close, window=ema_slow)

    macd = ta.trend.MACD(close, window_fast=macd_fast, window_slow=macd_slow, window_sign=macd_signal)
    df["macd_line"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()

    df["rsi"] = ta.momentum.rsi(close, window=rsi_period)

    plus_di, minus_di, adx = tradingview_dmi_adx(high, low, close, length=dmi_period)
    df["adx"] = adx
    df["plus_di"] = plus_di
    df["minus_di"] = minus_di

    last = df.iloc[-1]

    fig = go.Figure()

    fig.add_trace(
        go.Candlestick(
            x=df["date"], open=df["open"], high=df["high"],
            low=df["low"], close=df["close"], name="Price",
            increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
        ),
    )
    fig.add_trace(
        go.Scatter(x=df["date"], y=df["ema_fast"], name=f"EMA {ema_fast}",
                   line=dict(color="#2196f3", width=1.5)),
    )
    fig.add_trace(
        go.Scatter(x=df["date"], y=df["ema_slow"], name=f"EMA {ema_slow}",
                   line=dict(color="#ff9800", width=1.5)),
    )

    today_str = date.today().strftime("%Y-%m-%d")
    display_today = date.today().strftime("%d/%m/%Y")
    all_signals = detect_all_signals(df, today=display_today if not is_market_closed() else None)
    if all_signals:
        buy_dates = [s[0] for s in all_signals if s[1] == "BUY"]
        buy_prices = [s[2] for s in all_signals if s[1] == "BUY"]
        sell_dates = [s[0] for s in all_signals if s[1] == "SELL"]
        sell_prices = [s[2] for s in all_signals if s[1] == "SELL"]

        if buy_dates:
            fig.add_trace(
                go.Scatter(
                    x=buy_dates, y=buy_prices,
                    mode="markers",
                    marker=dict(symbol="triangle-up", size=20, color="#00e676",
                                line=dict(width=2, color="#00c853")),
                    name="BUY",
                    hovertemplate="BUY<br>Date: %{x}<br>Price: %{y:.2f}<extra></extra>",
                ),
            )
        if sell_dates:
            fig.add_trace(
                go.Scatter(
                    x=sell_dates, y=sell_prices,
                    mode="markers",
                    marker=dict(symbol="triangle-down", size=20, color="#ff1744",
                                line=dict(width=2, color="#d50000")),
                    name="SELL",
                    hovertemplate="SELL<br>Date: %{x}<br>Price: %{y:.2f}<extra></extra>",
                ),
            )

    fig.update_layout(
        title=f"{symbol} — {last['date']}",
        height=600,
        xaxis_rangeslider_visible=False,
        showlegend=True,
        margin=dict(l=50, r=20, t=40, b=20),
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="#eee", tickformat="%d/%m/%Y")
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="#eee")

    result = detect_signal(df, today=display_today if not is_market_closed() else None)

    price_change = None
    if all_signals and len(all_signals) >= 2:
        pair = None

        last_buy = None
        for sig in all_signals:
            if sig[1] == "BUY":
                last_buy = sig
        if last_buy:
            for sig in all_signals:
                if sig[0] > last_buy[0] and sig[1] == "SELL":
                    pair = (last_buy, sig)
                    break

        last_sell = None
        for sig in all_signals:
            if sig[1] == "SELL":
                last_sell = sig
        if last_sell:
            for sig in all_signals:
                if sig[0] > last_sell[0] and sig[1] == "BUY":
                    sell_buy = (last_sell, sig)
                    if pair is None or sell_buy[1][0] > pair[1][0]:
                        pair = sell_buy
                    break

        if pair:
            from_date, from_type, from_price = pair[0]
            to_date, to_type, to_price = pair[1]
            pct = (to_price - from_price) / from_price * 100
            price_change = {
                "from_type": from_type,
                "from_date": from_date,
                "from_price": from_price,
                "to_type": to_type,
                "to_date": to_date,
                "to_price": to_price,
                "pct": pct,
            }

    daily_change = None
    if len(df) >= 2:
        prev_close = df.iloc[-2]["close"]
        curr_close = last["close"]
        if prev_close and prev_close != 0:
            daily_pct = (curr_close - prev_close) / prev_close * 100
            daily_change = {
                "prev_close": prev_close,
                "curr_close": curr_close,
                "pct": daily_pct,
            }

    return {
        "figure": fig,
        "signal": result,
        "all_signals": all_signals,
        "price_change": price_change,
        "daily_change": daily_change,
        "last": {
            "date": last["date"],
            "close": last["close"],
            "ema_fast": last["ema_fast"],
            "ema_slow": last["ema_slow"],
            "rsi": last["rsi"],
            "adx": last["adx"],
            "plus_di": last["plus_di"],
            "minus_di": last["minus_di"],
            "macd_hist": last["macd_hist"],
        },
    }
