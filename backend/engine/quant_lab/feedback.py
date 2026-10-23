"""Live feedback loop: scores what actually happened to settled user trades, per asset and signal source.

Read-only on users.db; writes only quant_lab.db (`live_feedback`). Trades don't carry a Quant Lab
strategy_id, so attribution is by asset + signal_source (not per strategy): this tells research which
markets/signals are really paying in live and paper use, and how well-calibrated the predicted
probability was (Brier vs the trade's own `probability_percent`).
"""
import json
import logging
import os
import sqlite3
import time
from collections import defaultdict
from typing import Dict, Optional

logger = logging.getLogger("QuantLabFeedback")

_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
_USERS = os.path.join(_BASE, "users.db")
_QL = os.path.join(_BASE, "quant_lab.db")

# ticker prefix -> asset key (longest prefix wins)
PREFIX = {
    "KXBTC": "BTC", "KXETH": "ETH", "KXSOL": "SOL", "KXDOGE": "DOGE", "KXGOLD": "GOLD",
    "KXEURUSD": "EURUSD", "KXGBPUSD": "GBPUSD", "KXUSDJPY": "USDJPY", "KXAUDUSD": "AUDUSD", "KXNASDAQ": "NDQ",
    "KXNFL": "NFL", "KXMLB": "MLB", "KXNHL": "NHL", "KXNBA": "NBA", "KXNCAAF": "NCAAF", "KXNPB": "NPB",
    "KXKBO": "KBO", "KXEPL": "EPL", "KXMLS": "MLS", "KXUFC": "UFC", "KXATP": "TEN", "KXWTA": "TEN",
    "KXLALIGA": "SOC", "KXBUNDESLIGA": "SOC", "KXSERIEA": "SOC",
}
MIN_N = 10  # below this a row is informational only


def _asset(ticker: str) -> str:
    t = (ticker or "").upper()
    for p in sorted(PREFIX, key=len, reverse=True):
        if t.startswith(p):
            return PREFIX[p]
    return "OTHER"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_QL, timeout=30)
    c.execute(
        """CREATE TABLE IF NOT EXISTS live_feedback (
            asset TEXT, signal_source TEXT, n INTEGER, wins INTEGER, pnl REAL, avg_entry REAL,
            avg_pred REAL, brier REAL, updated_at REAL, PRIMARY KEY (asset, signal_source))"""
    )
    return c


def refresh() -> Dict[str, dict]:
    """Recompute the table from settled trades (one row per ticker+side, newest wins)."""
    u = sqlite3.connect(f"file:{_USERS}?mode=ro", uri=True, timeout=30)
    try:
        rows = u.execute(
            "SELECT ticker, side, entry_price, pnl, signal_source, raw_json FROM trades "
            "WHERE status='CLOSED' AND pnl IS NOT NULL ORDER BY settled_at DESC"
        ).fetchall()
    finally:
        u.close()

    seen = set()
    agg = defaultdict(lambda: {"n": 0, "wins": 0, "pnl": 0.0, "entry": 0.0, "pred_n": 0, "pred": 0.0, "brier": 0.0})
    for ticker, side, entry, pnl, src, raw in rows:
        key = (ticker, side)
        if key in seen:
            continue
        seen.add(key)
        a = agg[(_asset(ticker), (src or "UNKNOWN").upper())]
        win = 1 if pnl > 0 else 0
        a["n"] += 1
        a["wins"] += win
        a["pnl"] += float(pnl)
        a["entry"] += float(entry or 0)
        try:
            pp = float(json.loads(raw).get("probability_percent")) / 100.0
            if 0 < pp <= 1:
                a["pred_n"] += 1
                a["pred"] += pp
                a["brier"] += (pp - win) ** 2
        except Exception:
            pass

    now = time.time()
    out = {}
    c = _conn()
    try:
        for (asset, src), a in agg.items():
            n = a["n"]
            rec = {
                "n": n, "wins": a["wins"], "pnl": round(a["pnl"], 2), "avg_entry": round(a["entry"] / n, 3),
                "avg_pred": round(a["pred"] / a["pred_n"], 3) if a["pred_n"] else None,
                "brier": round(a["brier"] / a["pred_n"], 4) if a["pred_n"] else None,
            }
            out[f"{asset}/{src}"] = rec
            c.execute(
                "INSERT OR REPLACE INTO live_feedback VALUES (?,?,?,?,?,?,?,?,?)",
                (asset, src, n, a["wins"], rec["pnl"], rec["avg_entry"], rec["avg_pred"], rec["brier"], now),
            )
        c.commit()
    finally:
        c.close()
    return out


def live_context(asset: str) -> Optional[str]:
    """One-line live-results summary for an asset (None when too little data)."""
    try:
        c = _conn()
        try:
            rows = c.execute(
                "SELECT n, wins, pnl FROM live_feedback WHERE asset=?", (asset.upper(),)
            ).fetchall()
        finally:
            c.close()
        n = sum(r[0] for r in rows)
        if n < MIN_N:
            return None
        wins = sum(r[1] for r in rows)
        pnl = sum(r[2] for r in rows)
        return f"Live results for {asset}: {n} settled trades, {wins / n:.0%} win rate, net ${pnl:+.2f}."
    except Exception:
        return None


_scale_cache: Dict[str, tuple] = {}
SCALE_MIN_N = 40        # settled trades needed before any scaling
SCALE_FLOOR = 0.5       # never cut live size below half of the user's setting
SCALE_MARGIN = 0.03     # win rate must trail the average entry price by this much


def size_scale(ticker: str) -> float:
    """Size multiplier for live order sizing.
    Always returns 1.0 so user-configured bid size is not halved or scaled down.
    """
    return 1.0

