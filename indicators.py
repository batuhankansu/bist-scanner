import pandas as pd
import ta

import numpy as np


def rma(series: pd.Series, length: int) -> pd.Series:
    """
    TradingView ta.rma() karşılığı.
    Wilder Moving Average
    """
    alpha = 1.0 / length
    return series.ewm(alpha=alpha, adjust=False).mean()


def tradingview_dmi_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int = 4,
):
    """
    Pine Script'teki:

    plusDI
    minusDI
    adx

    hesaplamasının Python karşılığı.
    """

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where(
        (up_move > down_move) & (up_move > 0),
        up_move,
        0.0,
    )

    minus_dm = np.where(
        (down_move > up_move) & (down_move > 0),
        down_move,
        0.0,
    )

    plus_dm = pd.Series(plus_dm, index=high.index)
    minus_dm = pd.Series(minus_dm, index=high.index)

    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    trur = rma(tr, length)

    plus_di = 100.0 * rma(plus_dm, length) / trur
    minus_di = 100.0 * rma(minus_dm, length) / trur

    dx = (
        (plus_di - minus_di).abs()
        / (plus_di + minus_di)
        * 100.0
    )

    adx = rma(dx, length)

    return plus_di, minus_di, adx

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    close = df["close"]
    high = df["high"]
    low = df["low"]

    df["ema_fast"] = ta.trend.ema_indicator(close, window=7)
    df["ema_slow"] = ta.trend.ema_indicator(close, window=21)

    macd = ta.trend.MACD(close, window_fast=10, window_slow=18, window_sign=9)
    df["macd_line"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()

    df["rsi"] = ta.momentum.rsi(close, window=14)

    plus_di, minus_di, adx = tradingview_dmi_adx(
    high,
    low,
    close,
    length=4
    )

    df["adx"] = adx
    df["plus_di"] = plus_di
    df["minus_di"] = minus_di

    return df
