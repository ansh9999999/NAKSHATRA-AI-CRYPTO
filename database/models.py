"""NAKSHATRA AI trade database models."""
from __future__ import annotations

from database.database import get_connection


def save_trade(trade):
    conn = get_connection()
    try:
        conn.execute("""
        INSERT INTO trades(
            trade_time, symbol, signal, entry, stop_loss, target,
            exit_price, pnl, score, trend, volume, liquidity, result
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            trade["trade_time"], trade["symbol"], trade["signal"],
            trade.get("entry"), trade.get("stop_loss"), trade.get("target"),
            trade.get("exit_price"), trade.get("pnl", 0), trade.get("score", 0),
            trade.get("trend"), trade.get("volume"), trade.get("liquidity"),
            trade.get("result", "OPEN"),
        ))
        conn.commit()
    finally:
        conn.close()


def get_all_trades():
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM trades ORDER BY id DESC").fetchall()
    finally:
        conn.close()


def get_open_trades():
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT * FROM trades WHERE result='OPEN' ORDER BY id DESC
        """).fetchall()
    finally:
        conn.close()


def update_trade(trade_id, exit_price, pnl, result):
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE trades
            SET exit_price=?, pnl=?, result=?
            WHERE id=?
        """, (exit_price, pnl, result, trade_id))
        conn.commit()
    finally:
        conn.close()


def update_stop_loss(trade_id, stop_loss):
    conn = get_connection()
    try:
        conn.execute("UPDATE trades SET stop_loss=? WHERE id=?", (stop_loss, trade_id))
        conn.commit()
    finally:
        conn.close()


def update_target(trade_id, target):
    conn = get_connection()
    try:
        conn.execute("UPDATE trades SET target=? WHERE id=?", (target, trade_id))
        conn.commit()
    finally:
        conn.close()


def update_trade_levels(trade_id, stop_loss, target):
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE trades SET stop_loss=?, target=? WHERE id=?
        """, (stop_loss, target, trade_id))
        conn.commit()
    finally:
        conn.close()


def delete_trade(trade_id):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM trades WHERE id=?", (trade_id,))
        conn.commit()
    finally:
        conn.close()


def trade_count():
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    finally:
        conn.close()
