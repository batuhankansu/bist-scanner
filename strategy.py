import pandas as pd

from config import NEAR_CROSS_PCT, RSI_BUY_LEVEL, RSI_SELL_LEVEL, ADX_MIN, MIN_BARS


def detect_signal(df: pd.DataFrame, today: str | None = None) -> tuple[str, float] | None:
    if len(df) < 3:
        return None

    if today and len(df) >= 2 and str(df.iloc[-1]["date"]) == today:
        check_df = df.iloc[:-1]
    else:
        check_df = df

    if len(check_df) < 3:
        return None

    last = check_df.iloc[-1]
    prev = check_df.iloc[-2]

    ema_fast = last["ema_fast"]
    ema_slow = last["ema_slow"]
    prev_ema_fast = prev["ema_fast"]
    prev_ema_slow = prev["ema_slow"]

    if pd.isna(ema_fast) or pd.isna(ema_slow) or pd.isna(prev_ema_fast) or pd.isna(prev_ema_slow):
        return None

    cross_up = prev_ema_fast <= prev_ema_slow and ema_fast > ema_slow
    cross_down = prev_ema_fast >= prev_ema_slow and ema_fast < ema_slow

    dist_pct = abs(ema_fast - ema_slow) / ema_slow * 100.0 if ema_slow != 0 else 999.0
    slope_fast = ema_fast - prev_ema_fast
    slope_slow = ema_slow - prev_ema_slow

    near_cross_up = (dist_pct <= NEAR_CROSS_PCT) and (slope_fast > slope_slow)
    near_cross_down = (dist_pct <= NEAR_CROSS_PCT) and (slope_fast < 0)

    ema_ok_buy = cross_up or near_cross_up
    ema_ok_sell = cross_down or (near_cross_down and slope_fast < 0)

    macd_line = last["macd_line"]
    signal_line = last["macd_signal"]
    hist = last["macd_hist"]
    prev_macd = prev["macd_line"]
    prev_signal = prev["macd_signal"]
    prev_hist = prev["macd_hist"]

    if pd.isna(macd_line) or pd.isna(signal_line) or pd.isna(hist):
        return None

    macd_bull = (prev_macd <= prev_signal and macd_line > signal_line) or (macd_line > signal_line and hist > 0)
    macd_bear = (prev_macd >= prev_signal and macd_line < signal_line) or (macd_line < signal_line and hist < 0)

    rsi = last["rsi"]
    if pd.isna(rsi):
        return None

    rsi_bull = rsi > RSI_BUY_LEVEL
    rsi_bear = rsi < RSI_SELL_LEVEL

    plus_di = last["plus_di"]
    minus_di = last["minus_di"]
    adx = last["adx"]

    if pd.isna(plus_di) or pd.isna(minus_di) or pd.isna(adx):
        return None

    dmi_bull = plus_di > minus_di and adx >= ADX_MIN
    dmi_bear = minus_di > plus_di and adx >= ADX_MIN

    if ema_ok_buy and macd_bull and rsi_bull and dmi_bull:
        return ("BUY", last["close"])
    elif ema_ok_sell and macd_bear and rsi_bear and dmi_bear:
        return ("SELL", last["close"])

    return None


def detect_signal_debug(df: pd.DataFrame) -> dict | None:
    if len(df) < 3:
        return None

    last = df.iloc[-1]
    prev = df.iloc[-2]

    ema_fast = last["ema_fast"]
    ema_slow = last["ema_slow"]
    prev_ema_fast = prev["ema_fast"]
    prev_ema_slow = prev["ema_slow"]

    if pd.isna(ema_fast) or pd.isna(ema_slow) or pd.isna(prev_ema_fast) or pd.isna(prev_ema_slow):
        return None

    cross_up = prev_ema_fast <= prev_ema_slow and ema_fast > ema_slow
    cross_down = prev_ema_fast >= prev_ema_slow and ema_fast < ema_slow
    dist_pct = abs(ema_fast - ema_slow) / ema_slow * 100.0 if ema_slow != 0 else 999.0
    slope_fast = ema_fast - prev_ema_fast
    slope_slow = ema_slow - prev_ema_slow
    near_cross_up = (dist_pct <= NEAR_CROSS_PCT) and (slope_fast > slope_slow)
    near_cross_down = (dist_pct <= NEAR_CROSS_PCT) and (slope_fast < 0)
    ema_ok_buy = cross_up or near_cross_up
    ema_ok_sell = cross_down or (near_cross_down and slope_fast < 0)

    macd_line = last["macd_line"]
    signal_line = last["macd_signal"]
    hist = last["macd_hist"]
    prev_macd = prev["macd_line"]
    prev_signal = prev["macd_signal"]

    if pd.isna(macd_line) or pd.isna(signal_line) or pd.isna(hist):
        return None

    macd_bull = (prev_macd <= prev_signal and macd_line > signal_line) or (macd_line > signal_line and hist > 0)
    macd_bear = (prev_macd >= prev_signal and macd_line < signal_line) or (macd_line < signal_line and hist < 0)

    rsi = last["rsi"]
    if pd.isna(rsi):
        return None

    plus_di = last["plus_di"]
    minus_di = last["minus_di"]
    adx = last["adx"]

    if pd.isna(plus_di) or pd.isna(minus_di) or pd.isna(adx):
        return None

    dmi_bull = plus_di > minus_di and adx >= ADX_MIN
    dmi_bear = minus_di > plus_di and adx >= ADX_MIN

    rsi_bull = rsi > RSI_BUY_LEVEL
    rsi_bear = rsi < RSI_SELL_LEVEL

    signal = None
    if ema_ok_buy and macd_bull and rsi_bull and dmi_bull:
        signal = "BUY"
    elif ema_ok_sell and macd_bear and rsi_bear and dmi_bear:
        signal = "SELL"

    return {
        "signal": signal,
        "date": last["date"],
        "close": last["close"],
        "ema_fast": round(ema_fast, 4),
        "ema_slow": round(ema_slow, 4),
        "dist_pct": round(dist_pct, 4),
        "slope_fast": round(slope_fast, 4),
        "slope_slow": round(slope_slow, 4),
        "cross_up": cross_up,
        "cross_down": cross_down,
        "near_cross_up": near_cross_up,
        "near_cross_down": near_cross_down,
        "ema_ok_buy": ema_ok_buy,
        "ema_ok_sell": ema_ok_sell,
        "macd": round(macd_line, 4),
        "macd_signal": round(signal_line, 4),
        "macd_hist": round(hist, 4),
        "macd_bull": macd_bull,
        "macd_bear": macd_bear,
        "rsi": round(rsi, 2),
        "rsi_bull": rsi_bull,
        "rsi_bear": rsi_bear,
        "plus_di": round(plus_di, 2),
        "minus_di": round(minus_di, 2),
        "adx": round(adx, 2),
        "dmi_bull": dmi_bull,
        "dmi_bear": dmi_bear,
    }


def detect_all_signals(df: pd.DataFrame, today: str | None = None) -> list[tuple[str, str, float]]:
    """Detect signals on all historical bars.
    Returns list of (date, signal_type, close_price).
    Indicators must already be computed on df.
    If today is provided, skips the last bar if it matches today's date.
    """
    end = len(df)
    if today and end >= 1 and str(df.iloc[-1]["date"]) == today:
        end -= 1

    signals = []
    for i in range(MIN_BARS, end):
        sub = df.iloc[: i + 1]
        result = detect_signal(sub)
        if result:
            signals.append((sub.iloc[-1]["date"], result[0], result[1]))
    return signals
