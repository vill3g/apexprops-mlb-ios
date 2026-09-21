import os
import json
import sqlite3
import logging
import threading
import time
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DEFAULT_DB_PATH = os.path.join(DATA_DIR, "trades.db")


class TradeDB:
    """
    High-performance SQLite repository for trades history.
    Uses Write-Ahead Logging (WAL) mode to permit concurrent reads without blocking writes.
    Provides atomic upserts and full backward-compatible dictionary serialization.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    def _init_db(self):
        with self._lock:
            conn = self._get_connection()
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS trades (
                        id TEXT PRIMARY KEY,
                        asset TEXT NOT NULL,
                        ticker TEXT,
                        timestamp TEXT,
                        interval_close_time TEXT,
                        close_epoch REAL,
                        strike REAL,
                        side TEXT,
                        direction TEXT,
                        entry_price REAL,
                        exit_price REAL,
                        count REAL,
                        cost REAL,
                        mode TEXT,
                        status TEXT,
                        result TEXT,
                        pnl REAL,
                        realized_pnl REAL,
                        exit_reason TEXT,
                        raw_json TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_asset_status ON trades(asset, status);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_asset_created ON trades(asset, created_at);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker);")

    def upsert_trade(self, trade: Dict[str, Any], asset: str = "BTC") -> bool:
        """Atomically insert or update a single trade."""
        return self.upsert_trades([trade], asset=asset)

    def upsert_trades(self, trades: List[Dict[str, Any]], asset: str = "BTC") -> bool:
        """Batch upsert trades in a single ACID transaction."""
        if not trades:
            return True

        rows = []
        now_ts = time.time()
        for idx, t in enumerate(trades):
            trade_id = str(t.get("id") or f"trade_{int(now_ts * 1000)}_{idx}")
            ticker = t.get("ticker")
            ts_str = t.get("timestamp")
            int_close = t.get("interval_close_time")
            close_ep = float(t.get("close_epoch", 0.0) or 0.0)
            strike = float(t.get("strike", 0.0) or 0.0)
            side = t.get("side")
            direction = t.get("direction")
            entry_p = float(t.get("entry_price", 0.0) or 0.0)
            exit_p = float(t.get("exit_price", 0.0) or 0.0) if t.get("exit_price") is not None else None
            count = float(t.get("count", 1.0) or 1.0)
            cost = float(t.get("cost", 0.0) or 0.0)
            mode = str(t.get("mode", "PAPER")).upper()
            status = str(t.get("status", "OPEN")).upper()
            result = str(t.get("result", "PENDING")).upper()
            pnl = float(t.get("pnl", 0.0) or 0.0)
            realized_pnl = float(t.get("realized_pnl", 0.0) or 0.0)
            exit_reason = t.get("exit_reason")
            raw_json = json.dumps(t, ensure_ascii=False)
            
            # preserve original ordering via index if close_epoch not set
            created_at = close_ep if close_ep > 0 else (now_ts - (len(trades) - idx) * 900)

            rows.append((
                trade_id, asset, ticker, ts_str, int_close, close_ep, strike,
                side, direction, entry_p, exit_p, count, cost, mode, status,
                result, pnl, realized_pnl, exit_reason, raw_json, created_at, now_ts
            ))

        with self._lock:
            try:
                conn = self._get_connection()
                with conn:
                    conn.executemany("""
                        INSERT INTO trades (
                            id, asset, ticker, timestamp, interval_close_time, close_epoch,
                            strike, side, direction, entry_price, exit_price, count, cost,
                            mode, status, result, pnl, realized_pnl, exit_reason, raw_json,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            ticker=excluded.ticker,
                            timestamp=excluded.timestamp,
                            interval_close_time=excluded.interval_close_time,
                            close_epoch=excluded.close_epoch,
                            strike=excluded.strike,
                            side=excluded.side,
                            direction=excluded.direction,
                            entry_price=excluded.entry_price,
                            exit_price=excluded.exit_price,
                            count=excluded.count,
                            cost=excluded.cost,
                            mode=excluded.mode,
                            status=excluded.status,
                            result=excluded.result,
                            pnl=excluded.pnl,
                            realized_pnl=excluded.realized_pnl,
                            exit_reason=excluded.exit_reason,
                            raw_json=excluded.raw_json,
                            updated_at=excluded.updated_at;
                    """, rows)
                return True
            except Exception as e:
                logger.error(f"[TradeDB] Error upserting trades: {e}", exc_info=True)
                return False

    def get_trades(
        self,
        asset: str = "BTC",
        limit: Optional[int] = None,
        status: Optional[str] = None,
        mode: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve trades for an asset in chronological order."""
        with self._lock:
            try:
                conn = self._get_connection()
                query = "SELECT raw_json FROM trades WHERE asset = ?"
                params: List[Any] = [asset]

                if status:
                    query += " AND status = ?"
                    params.append(status.upper())
                if mode:
                    query += " AND mode = ?"
                    params.append(mode.upper())

                query += " ORDER BY created_at ASC"

                if limit and limit > 0:
                    query += " LIMIT ?"
                    params.append(limit)

                cursor = conn.execute(query, params)
                trades = []
                for row in cursor:
                    try:
                        trades.append(json.loads(row["raw_json"]))
                    except Exception as je:
                        logger.warning(f"[TradeDB] Malformed trade row JSON skipped: {je}")
                return trades
            except Exception as e:
                logger.error(f"[TradeDB] Error querying trades: {e}")
                return []

    def count_trades(self, asset: str = "BTC") -> int:
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.execute("SELECT COUNT(*) FROM trades WHERE asset = ?", (asset,))
                return int(cursor.fetchone()[0])
            except Exception as e:
                logger.error(f"[TradeDB] Error counting trades: {e}")
                return 0

    def import_from_json_if_needed(self, json_path: str, asset: str = "BTC") -> int:
        """
        One-time / startup synchronization:
        If the SQLite table has fewer trades than the JSON backup file,
        bulk-import the JSON file into SQLite.
        """
        if not os.path.exists(json_path):
            return 0

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                trades = json.load(f)
            if not isinstance(trades, list) or not trades:
                return 0

            db_count = self.count_trades(asset=asset)
            if db_count < len(trades):
                logger.info(f"[TradeDB] Importing {len(trades)} trades from {json_path} into SQLite (current DB count: {db_count})...")
                self.upsert_trades(trades, asset=asset)
                new_count = self.count_trades(asset=asset)
                logger.info(f"[TradeDB] SQLite import complete. Total rows in DB for {asset}: {new_count}")
                return len(trades)
        except Exception as e:
            logger.error(f"[TradeDB] Error during JSON migration into SQLite: {e}")
        return 0


# Singleton instance
_trade_db_instance = None
_trade_db_lock = threading.Lock()

def get_trade_db(db_path: str = DEFAULT_DB_PATH) -> TradeDB:
    global _trade_db_instance
    if _trade_db_instance is None:
        with _trade_db_lock:
            if _trade_db_instance is None:
                _trade_db_instance = TradeDB(db_path)
    return _trade_db_instance
