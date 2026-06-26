import pandas as pd


def detect_accumulation_signal(df: pd.DataFrame) -> dict | None:
    if len(df) < 3:
        return None

    last = df.iloc[-1]
    prev = df.iloc[-2]

    required = ["mfi", "cmf", "adx_14", "rsi_14", "ema_20", "vol_sma_20", "rel_volume", "close"]
    for col in required:
        if col not in df.columns or pd.isna(last[col]):
            return None
        if col != "close" and col != "vol_sma_20" and col != "rel_volume" and pd.isna(prev[col]):
            return None

    mfi_prev = prev["mfi"]
    mfi_curr = last["mfi"]
    mfi_cross_above = (not pd.isna(mfi_prev)) and mfi_prev <= 50 and mfi_curr > 50

    cmf_prev = prev["cmf"]
    cmf_curr = last["cmf"]
    cmf_cross_above = (not pd.isna(cmf_prev)) and cmf_prev <= 0 and cmf_curr > 0

    adx_val = last["adx_14"]
    adx_range = 15 <= adx_val <= 25

    rsi_prev = prev["rsi_14"]
    rsi_curr = last["rsi_14"]
    rsi_cross_above = (not pd.isna(rsi_prev)) and rsi_prev <= 50 and rsi_curr > 50

    close_val = last["close"]
    ema20_val = last["ema_20"]
    above_ema20 = close_val > ema20_val

    volume_val = last["volume"]
    vol_sma = last["vol_sma_20"]
    volume_surge = volume_val > vol_sma * 1.5 if not pd.isna(vol_sma) and vol_sma > 0 else False

    rel_vol = last["rel_volume"]
    high_rel_vol = rel_vol > 1.5 if not pd.isna(rel_vol) else False

    conditions = {
        "mfi_cross": mfi_cross_above,
        "cmf_cross": cmf_cross_above,
        "adx_range": adx_range,
        "rsi_cross": rsi_cross_above,
        "above_ema20": above_ema20,
        "volume_surge": volume_surge,
        "high_rel_volume": high_rel_vol,
    }

    all_met = all(conditions.values())

    return {
        "signal": "BUY" if all_met else None,
        "date": str(last["date"]),
        "close": close_val,
        "conditions": conditions,
        "values": {
            "mfi": round(mfi_curr, 2),
            "cmf": round(cmf_curr, 4),
            "adx": round(adx_val, 2),
            "rsi": round(rsi_curr, 2),
            "ema20": round(ema20_val, 2),
            "volume": int(volume_val),
            "vol_sma": int(vol_sma) if not pd.isna(vol_sma) else 0,
            "rel_volume": round(rel_vol, 2) if not pd.isna(rel_vol) else 0,
        },
    }


def detect_all_accumulation_signals(df: pd.DataFrame, today: str | None = None) -> list[dict]:
    from config import MIN_BARS

    end = len(df)
    if today and end >= 1 and str(df.iloc[-1]["date"]) == today:
        end -= 1

    signals = []
    for i in range(MIN_BARS, end):
        sub = df.iloc[: i + 1]
        result = detect_accumulation_signal(sub)
        if result and result["signal"] == "BUY":
            result["date"] = str(sub.iloc[-1]["date"])
            signals.append(result)
    return signals
