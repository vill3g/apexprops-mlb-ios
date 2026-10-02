"""Durable "one automated LIVE entry per account per market" guard.

Why this exists (audit finding M-DUP): when a LIVE order's HTTP response is lost (timeout,
dropped connection), the bot can't tell whether it filled. The in-memory guards
(`last_traded_interval`, the SaaS per-user cache, inflight_orders) either weren't set on
that path or live only in one process's memory, so a later loop - or the other process,
or the same process after a restart - could send the same real-money order again.

Before an automated LIVE entry is sent, the caller `claim()`s (account, ticker). The claim
is a row in users.db behind a UNIQUE constraint, so exactly one caller wins across threads,
processes and restarts. Outcome handling:
  * filled     -> `mark(..., "filled")`     keeps the claim (the market is traded)
  * ambiguous  -> `mark(..., "ambiguous")`  keeps the claim (it MAY have filled)
  * definitive rejection (Kalshi said no, nothing sent, unfilled IOC) -> `release()`
    so the bot may try again later in the same interval, as it did before.

Each 15-minute market has its own ticker, so a claim naturally only blocks that market.
Manual trades, second entries and the RL scalper do not go through this guard.
"""
import logging
import sqlite3
import time
from typing import Optional

logger = logging.getLogger(__name__)

_RETENTION_SECONDS = 3 * 86400
_last_purge = 0.0


def _connect() -> sqlite3.Connection:
    # A short-lived dedicated connection (not the shared thread-local one) so a claim is
    # committed immediately and never gets mixed into another caller's open transaction.
    from backend.database import models
    conn = sqlite3.connect(models.DB_PATH, timeout=10.0)
    conn.execute("PRAGMA busy_timeout=10000;")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS order_intents (
               account_key     TEXT NOT NULL,
               ticker          TEXT NOT NULL,
               side            TEXT,
               state           TEXT NOT NULL DEFAULT 'sending',
               client_order_id TEXT,
               created_at      REAL NOT NULL,
               updated_at      REAL NOT NULL,
               PRIMARY KEY (account_key, ticker)
           )"""
    )
    return conn


def account_key_for_user(user_id) -> str:
    return f"user:{int(user_id)}"


def account_key_for_executor(guest_id: Optional[str] = None) -> str:
    return f"guest:{guest_id}" if guest_id else "owner"


def _maybe_purge(conn: sqlite3.Connection) -> None:
    global _last_purge
    now = time.time()
    if now - _last_purge < 3600:
        return
    _last_purge = now
    conn.execute("DELETE FROM order_intents WHERE updated_at < ?", (now - _RETENTION_SECONDS,))


def claim(account_key: str, ticker: str, side: str = "") -> bool:
    """True if this caller now owns the single automated LIVE entry for (account, ticker).
    False if one was already claimed - or if the claim can't be recorded (fail closed:
    with real money, not trading is the safe failure)."""
    if not account_key or not ticker:
        return False
    now = time.time()
    try:
        conn = _connect()
        try:
            with conn:
                _maybe_purge(conn)
                cur = conn.execute(
                    "INSERT OR IGNORE INTO order_intents "
                    "(account_key, ticker, side, state, created_at, updated_at) "
                    "VALUES (?, ?, ?, 'sending', ?, ?)",
                    (account_key, str(ticker), str(side or "").upper(), now, now),
                )
                return cur.rowcount == 1
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"[OrderIntents] Could not record order intent for {account_key} on {ticker}: {e}. "
                     f"Skipping this LIVE entry (fail closed).")
        return False


def mark(account_key: str, ticker: str, state: str, client_order_id: Optional[str] = None) -> None:
    try:
        conn = _connect()
        try:
            with conn:
                conn.execute(
                    "UPDATE order_intents SET state = ?, client_order_id = COALESCE(?, client_order_id), "
                    "updated_at = ? WHERE account_key = ? AND ticker = ?",
                    (state, client_order_id, time.time(), account_key, str(ticker)),
                )
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"[OrderIntents] Could not mark {account_key} {ticker} as {state}: {e}")


def release(account_key: str, ticker: str) -> None:
    """Only call this when the order definitely did NOT fill."""
    try:
        conn = _connect()
        try:
            with conn:
                conn.execute("DELETE FROM order_intents WHERE account_key = ? AND ticker = ?",
                             (account_key, str(ticker)))
        finally:
            conn.close()
    except Exception as e:
        # The claim stays; the worst case is skipping the rest of this interval.
        logger.error(f"[OrderIntents] Could not release {account_key} {ticker}: {e}")


def get(account_key: str, ticker: str) -> Optional[dict]:
    try:
        conn = _connect()
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM order_intents WHERE account_key = ? AND ticker = ?",
                               (account_key, str(ticker))).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    except Exception:
        return None


def settle_outcome(account_key: str, ticker: str, order_res: dict) -> str:
    """Apply a place_order() result to the claim. Returns 'filled', 'ambiguous' or 'released'."""
    order_res = order_res or {}
    cid = order_res.get("client_order_id")
    if order_res.get("success"):
        mark(account_key, ticker, "filled", cid)
        return "filled"
    if order_res.get("ambiguous"):
        mark(account_key, ticker, "ambiguous", cid)
        return "ambiguous"
    release(account_key, ticker)
    return "released"
