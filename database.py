import sqlite3
from datetime import date, datetime
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ohlcv (
            symbol TEXT NOT NULL,
            date   TEXT NOT NULL,
            open   REAL,
            high   REAL,
            low    REAL,
            close  REAL,
            volume INTEGER,
            PRIMARY KEY (symbol, date)
        );
        CREATE TABLE IF NOT EXISTS signals (
            symbol      TEXT NOT NULL,
            signal_date TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            close_price REAL,
            PRIMARY KEY (symbol, signal_date, signal_type)
        );
        CREATE TABLE IF NOT EXISTS scan_metadata (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    conn.execute("DELETE FROM ohlcv WHERE volume = 0")
    conn.commit()
    conn.close()


def get_last_date(symbol: str) -> str | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT MAX(date) FROM ohlcv WHERE symbol = ?", (symbol,)
    ).fetchone()
    conn.close()
    return row[0] if row and row[0] else None


def insert_ohlcv(symbol: str, rows: list[tuple]):
    conn = get_conn()
    conn.executemany(
        "INSERT OR REPLACE INTO ohlcv (symbol, date, open, high, low, close, volume) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(symbol, *r) for r in rows],
    )
    conn.commit()
    conn.close()


def load_ohlcv(symbol: str, limit: int = 100) -> list[tuple]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT date, open, high, low, close, volume "
        "FROM ohlcv WHERE symbol = ? ORDER BY date DESC LIMIT ?",
        (symbol, limit),
    ).fetchall()
    conn.close()
    return list(reversed(rows))


def insert_signal(symbol: str, signal_date: str, signal_type: str, close_price: float):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO signals (symbol, signal_date, signal_type, close_price) "
        "VALUES (?, ?, ?, ?)",
        (symbol, signal_date, signal_type, close_price),
    )
    conn.commit()
    conn.close()


def get_latest_signal(symbol: str) -> tuple | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT signal_date, signal_type, close_price "
        "FROM signals WHERE symbol = ? ORDER BY signal_date DESC LIMIT 1",
        (symbol,),
    ).fetchone()
    conn.close()
    return row


def get_today_signals(today: str) -> list[tuple]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT symbol, signal_type, close_price "
        "FROM signals WHERE signal_date = ? ORDER BY signal_type, symbol",
        (today,),
    ).fetchall()
    conn.close()
    return rows


def get_previous_signals(today: str) -> list[tuple]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT s.symbol, s.signal_date, s.signal_type, s.close_price "
        "FROM signals s "
        "INNER JOIN (SELECT symbol, MAX(signal_date) AS max_date FROM signals GROUP BY symbol) latest "
        "ON s.symbol = latest.symbol AND s.signal_date = latest.max_date "
        "WHERE s.signal_date != ? "
        "ORDER BY s.signal_date DESC, s.symbol",
        (today,),
    ).fetchall()
    conn.close()
    return rows


def set_scan_time():
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO scan_metadata (key, value) VALUES ('last_scan', ?)",
        (datetime.now().isoformat(),),
    )
    conn.commit()
    conn.close()


def get_scan_time() -> str | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT value FROM scan_metadata WHERE key = 'last_scan'"
    ).fetchone()
    conn.close()
    return row[0] if row else None
