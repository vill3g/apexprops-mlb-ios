"""
Persistent Strategy Graveyard & Memory Store for ShadowTrader Quant Lab.
Retains a persistent negative knowledge base of failed trading hypotheses,
loss post-mortems, and regime-specific failure constraints.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "quant_lab.db")
)
_db_lock = threading.Lock()


def _get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize database tables for Quant Lab registry and graveyard."""
    with _db_lock, _get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS strategy_graveyard (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT NOT NULL,
                name TEXT NOT NULL,
                hypothesis TEXT NOT NULL,
                code_hash TEXT,
                asset TEXT NOT NULL,
                target_interval TEXT DEFAULT '15m',
                failure_stage TEXT NOT NULL,
                metrics_snapshot TEXT,
                regime_context TEXT,
                post_mortem_summary TEXT NOT NULL,
                negative_rule TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_graveyard_asset ON strategy_graveyard(asset)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_graveyard_stage ON strategy_graveyard(failure_stage)
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS strategy_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                hypothesis TEXT NOT NULL,
                asset TEXT NOT NULL,
                target_interval TEXT DEFAULT '15m',
                code TEXT NOT NULL,
                status TEXT NOT NULL,
                backtest_metrics TEXT,
                incubation_metrics TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_registry_status ON strategy_registry(status)
        """)
        conn.commit()


def _now_str() -> str:
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET")


class StrategyGraveyard:
    """Interface to read, record, and query the Strategy Graveyard."""

    @staticmethod
    def record_failure(
        strategy_id: str,
        name: str,
        hypothesis: str,
        asset: str,
        failure_stage: str,
        post_mortem_summary: str,
        negative_rule: str,
        code_hash: Optional[str] = None,
        target_interval: str = "15m",
        metrics_snapshot: Optional[Dict[str, Any]] = None,
        regime_context: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Commit a failed strategy or setup to the graveyard with full attribution.
        """
        init_db()
        metrics_json = json.dumps(metrics_snapshot or {})
        regime_json = json.dumps(regime_context or {})
        created_at = _now_str()

        with _db_lock, _get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO strategy_graveyard (
                    strategy_id, name, hypothesis, code_hash, asset,
                    target_interval, failure_stage, metrics_snapshot,
                    regime_context, post_mortem_summary, negative_rule, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                strategy_id, name, hypothesis, code_hash, asset.upper(),
                target_interval, failure_stage.upper(), metrics_json,
                regime_json, post_mortem_summary, negative_rule, created_at
            ))
            entry_id = cur.lastrowid
            
            # Also update registry status to GRAVEYARD if strategy exists
            cur.execute("""
                UPDATE strategy_registry
                SET status = 'GRAVEYARD', updated_at = ?
                WHERE strategy_id = ?
            """, (created_at, strategy_id))
            conn.commit()

        logger.info(f"[StrategyGraveyard] Recorded failure #{entry_id} for '{name}' ({asset}): {negative_rule}")
        return entry_id

    @staticmethod
    def get_entries(limit: int = 50, asset: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch graveyard records for inspection."""
        init_db()
        with _db_lock, _get_connection() as conn:
            cur = conn.cursor()
            if asset:
                rows = cur.execute("""
                    SELECT * FROM strategy_graveyard
                    WHERE asset = ? ORDER BY id DESC LIMIT ?
                """, (asset.upper(), limit)).fetchall()
            else:
                rows = cur.execute("""
                    SELECT * FROM strategy_graveyard
                    ORDER BY id DESC LIMIT ?
                """, (limit,)).fetchall()

            res = []
            for r in rows:
                d = dict(r)
                try:
                    d["metrics_snapshot"] = json.loads(d.get("metrics_snapshot") or "{}")
                except Exception:
                    d["metrics_snapshot"] = {}
                try:
                    d["regime_context"] = json.loads(d.get("regime_context") or "{}")
                except Exception:
                    d["regime_context"] = {}
                res.append(d)
            return res

    @staticmethod
    def get_relevant_lessons(asset: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Returns structured negative constraints and lessons learned to inject into
        the Alpha Ideator prompt context.
        """
        init_db()
        with _db_lock, _get_connection() as conn:
            cur = conn.cursor()
            fetch_limit = limit * 3
            if asset:
                rows = cur.execute("""
                    SELECT id, strategy_id, name, asset, failure_stage,
                           post_mortem_summary, negative_rule, created_at
                    FROM strategy_graveyard
                    WHERE asset = ? OR asset = 'ALL'
                    ORDER BY id DESC LIMIT ?
                """, (asset.upper(), fetch_limit)).fetchall()
            else:
                rows = cur.execute("""
                    SELECT id, strategy_id, name, asset, failure_stage,
                           post_mortem_summary, negative_rule, created_at
                    FROM strategy_graveyard
                    ORDER BY id DESC LIMIT ?
                """, (fetch_limit,)).fetchall()

            deduped = []
            seen_rules = set()
            for r in rows:
                d = dict(r)
                rule = (d.get("negative_rule") or "").strip().lower()
                if rule and rule not in seen_rules:
                    seen_rules.add(rule)
                    deduped.append(d)
                    if len(deduped) >= limit:
                        break
            return deduped

    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """Summary counts of failures by stage and asset."""
        init_db()
        with _db_lock, _get_connection() as conn:
            cur = conn.cursor()
            total = cur.execute("SELECT COUNT(*) FROM strategy_graveyard").fetchone()[0]
            by_stage = dict(cur.execute("SELECT failure_stage, COUNT(*) FROM strategy_graveyard GROUP BY failure_stage").fetchall())
            by_asset = dict(cur.execute("SELECT asset, COUNT(*) FROM strategy_graveyard GROUP BY asset").fetchall())
            return {
                "total_failures": total,
                "by_stage": by_stage,
                "by_asset": by_asset
            }


class StrategyRegistry:
    """Tracks strategies through their lifecycle: PROPOSED -> BACKTESTED -> INCUBATING -> GRADUATED."""

    @staticmethod
    def register(
        strategy_id: str,
        name: str,
        hypothesis: str,
        asset: str,
        code: str,
        target_interval: str = "15m",
        status: str = "PROPOSED"
    ) -> None:
        init_db()
        now = _now_str()
        with _db_lock, _get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO strategy_registry (
                    strategy_id, name, hypothesis, asset, target_interval,
                    code, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                strategy_id, name, hypothesis, asset.upper(), target_interval,
                code, status.upper(), now, now
            ))
            conn.commit()

    @staticmethod
    def update_status(
        strategy_id: str,
        status: str,
        backtest_metrics: Optional[Dict[str, Any]] = None,
        incubation_metrics: Optional[Dict[str, Any]] = None
    ) -> None:
        init_db()
        now = _now_str()
        with _db_lock, _get_connection() as conn:
            cur = conn.cursor()
            updates = ["status = ?", "updated_at = ?"]
            params = [status.upper(), now]

            if backtest_metrics is not None:
                updates.append("backtest_metrics = ?")
                params.append(json.dumps(backtest_metrics))
            if incubation_metrics is not None:
                updates.append("incubation_metrics = ?")
                params.append(json.dumps(incubation_metrics))

            params.append(strategy_id)
            cur.execute(f"""
                UPDATE strategy_registry
                SET {", ".join(updates)}
                WHERE strategy_id = ?
            """, params)
            conn.commit()

    @staticmethod
    def get_by_id(strategy_id: str) -> Optional[Dict[str, Any]]:
        init_db()
        with _db_lock, _get_connection() as conn:
            cur = conn.cursor()
            row = cur.execute("SELECT * FROM strategy_registry WHERE strategy_id = ?", (strategy_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["backtest_metrics"] = json.loads(d.get("backtest_metrics") or "{}")
            d["incubation_metrics"] = json.loads(d.get("incubation_metrics") or "{}")
            return d

    @staticmethod
    def list_strategies(status: Optional[str] = None, asset: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        init_db()
        with _db_lock, _get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT * FROM strategy_registry"
            clauses = []
            params: List[Any] = []
            if status:
                clauses.append("status = ?")
                params.append(status.upper())
            if asset:
                clauses.append("asset = ?")
                params.append(asset.upper())
            if clauses:
                query += " WHERE " + " AND ".join(clauses)
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)

            rows = cur.execute(query, params).fetchall()
            res = []
            for r in rows:
                d = dict(r)
                d["backtest_metrics"] = json.loads(d.get("backtest_metrics") or "{}")
                d["incubation_metrics"] = json.loads(d.get("incubation_metrics") or "{}")
                res.append(d)
            return res
