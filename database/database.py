"""SQLite database helpers for NAKSHATRA AI."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "trades.db")))


def get_connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DATABASE_PATH), timeout=30)
    conn.row_factory = None
    return conn


def initialize_database() -> None:
    conn = get_connection()
    try:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_time TEXT,
            symbol TEXT NOT NULL,
            signal TEXT NOT NULL,
            entry REAL,
            stop_loss REAL,
            target REAL,
            exit_price REAL,
            pnl REAL DEFAULT 0,
            score REAL DEFAULT 0,
            trend TEXT,
            volume REAL,
            liquidity REAL,
            result TEXT DEFAULT 'OPEN'
        )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_time ON trades(trade_time)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_result ON trades(result)")
        conn.commit()
    finally:
        conn.close()
