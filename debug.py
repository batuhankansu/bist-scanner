import sys
sys.path.insert(0, ".")

import pandas as pd
from database import init_db, load_ohlcv
from indicators import compute_indicators
from strategy import detect_signal_debug

init_db()

symbol = sys.argv[1] if len(sys.argv) > 1 else "BANVT"
rows = load_ohlcv(symbol, limit=100)

if len(rows) < 50:
    print(f"Not enough data for {symbol} ({len(rows)} bars)")
    sys.exit(1)

df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
df = compute_indicators(df)
d = detect_signal_debug(df)

if d is None:
    print(f"Could not compute signal for {symbol}")
    sys.exit(1)

print(f"\n{'='*50}")
print(f"  {symbol} — {d['date']} — Signal: {d['signal'] or 'NONE'}")
print(f"{'='*50}")

print(f"\n  EMA:  fast={d['ema_fast']}  slow={d['ema_slow']}")
print(f"  Dist: {d['dist_pct']}% (threshold: 0.40%)")
print(f"  Slope: fast={d['slope_fast']}  slow={d['slope_slow']}")
print(f"  CrossUp={d['cross_up']}  CrossDown={d['cross_down']}")
print(f"  NearUp={d['near_cross_up']}  NearDown={d['near_cross_down']}")
print(f"  EMA OK: buy={d['ema_ok_buy']}  sell={d['ema_ok_sell']}")

print(f"\n  MACD: {d['macd']}  Signal: {d['macd_signal']}  Hist: {d['macd_hist']}")
print(f"  MACD bull={d['macd_bull']}  bear={d['macd_bear']}")

print(f"\n  RSI: {d['rsi']}  bull(>47)={d['rsi_bull']}  bear(<55)={d['rsi_bear']}")

print(f"\n  +DI: {d['plus_di']}  -DI: {d['minus_di']}  ADX: {d['adx']}")
print(f"  DMI bull={d['dmi_bull']}  bear={d['dmi_bear']}")

print(f"\n  FINAL: EMA={d['ema_ok_buy']} AND MACD={d['macd_bull']} AND RSI={d['rsi_bull']} AND DMI={d['dmi_bull']}")
