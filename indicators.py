import pandas as pd
import ta

import numpy as np

from config import (
    EMA_FAST, EMA_SLOW,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    RSI_PERIOD, DMI_PERIOD,
)


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
    Pine Script'teki DMI/ADX hesaplamasının Python karşılığı.
    Wilder RMA kullanarak manuel hesaplama.
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

    df["ema_fast"] = ta.trend.ema_indicator(close, window=EMA_FAST)
    df["ema_slow"] = ta.trend.ema_indicator(close, window=EMA_SLOW)

    macd = ta.trend.MACD(close, window_fast=MACD_FAST, window_slow=MACD_SLOW, window_sign=MACD_SIGNAL)
    df["macd_line"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()

    df["rsi"] = ta.momentum.rsi(close, window=RSI_PERIOD)

    plus_di, minus_di, adx = tradingview_dmi_adx(
        high,
        low,
        close,
        length=DMI_PERIOD,
    )

    df["adx"] = adx
    df["plus_di"] = plus_di
    df["minus_di"] = minus_di

    return df
