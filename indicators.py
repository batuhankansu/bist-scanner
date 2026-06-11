import pandas as pd
import ta


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

    adx = ta.trend.ADXIndicator(high, low, close, window=4)
    df["adx"] = adx.adx()
    df["plus_di"] = adx.adx_pos()
    df["minus_di"] = adx.adx_neg()

    return df
