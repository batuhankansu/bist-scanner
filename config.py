import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

DB_PATH = BASE_DIR / "bist.db"

# EMA
EMA_FAST = 7
EMA_SLOW = 21
NEAR_CROSS_PCT = 0.40

# MACD
MACD_FAST = 10
MACD_SLOW = 18
MACD_SIGNAL = 9

# RSI
RSI_PERIOD = 14
RSI_BUY_LEVEL = 47.0
RSI_SELL_LEVEL = 55.0

# DMI / ADX
DMI_PERIOD = 4
ADX_MIN = 20.0

# Data
HISTORY_PERIOD = "6mo"
MIN_BARS = 50
YFINANCE_BATCH_SIZE = 50
