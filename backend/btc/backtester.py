"""AI Backtesting Engine ("Time Machine").

Replays a user's real closed trades from the last N days under *different* risk settings
(Take Profit %, Stop Loss %, Kelly Criterion gate/sizing, model / asset filters, fixed trade size)
and reports what the P&L would have been, side-by-side with what actually happened.

Data used per trade (all real, nothing synthetic):
  * entry_price / count / side / ticker             -> trades table
  * min_seen_bid  (lowest bid observed while open)   -> trades table
  * exit_price    (bid observed at the real exit)    -> trades table
  * official market outcome (YES / NO)               -> backend/data/market_results.json
  * probability_percent / model_choice               -> trades.raw_json

Replay rules (deliberately conservative):
  * SL is hit if the lowest observed bid touched the SL price, or if the contract later settled
    worthless (the bid must have passed through the SL price on its way to 0).
  * TP is hit if the bid observed at the real exit reached the TP price, or if the contract later
    settled in-the-money (the bid must have passed through the TP price on its way to $1).
  * If both SL and TP were touched while the real position was open, the order is unknown, so the
    SL is assumed to have fired first (pessimistic).
  * Winners that were closed early in reality have an unknown post-exit path; the chance they would
    have dipped through the new SL first is taken from the empirical drawdown distribution of winners
    that were held to settlement (expected-value exit, labelled ESTIMATED).
  * Peak bids are not recorded, so an eventual loser that briefly spiked through the TP is only
    detected via its real exit price -> TP benefit is UNDER-estimated (conservative).
  * Stops fill STOP_SLIPPAGE below the trigger; take-profits fill exactly at the trigger.
  * Kalshi fees are not modelled (consistent with the paper-trading ledger).
"""
from __future__ import annotations

import bisect
import json
import logging
import math
import os
import sqlite3
import time
from typing import Any, Dict, Iterable, List, Optional

from backend.database.models import get_db_connection, is_manual_entry
from backend.database.trade_store import _trade_epoch

logger = logging.getLogger(__name__)

KNOWN_ASSETS = ("BTC", "ETH", "SOL", "DOGE", "GOLD", "NDQ", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD")
STOP_SLIPPAGE = 0.02
MAX_DAYS = 90
_RESULTS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "market_results.json")

# market_results.json is rewritten by the settler; cache it keyed by mtime.
_results_cache: Dict[str, Any] = {"mtime": None, "data": {}}


def _load_market_results() -> Dict[str, str]:
    try:
        mtime = os.path.getmtime(_RESULTS_PATH)
        if _results_cache["mtime"] != mtime:
            with open(_RESULTS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            _results_cache["data"] = {str(k): str(v).upper() for k, v in (data or {}).items()}
            _results_cache["mtime"] = mtime
    except (OSError, ValueError) as e:
        logger.warning(f"[Backtester] Could not load market results: {e}")
    return _results_cache["data"]


def asset_from_ticker(ticker: Any) -> str:
    tk = str(ticker or "").upper()
    series = tk.split("-", 1)[0].replace("_SYNTH", "")
    if series.startswith("KX"):
        series = series[2:]
    if series.endswith("15M"):
        series = series[:-3]
    if series in KNOWN_ASSETS:
        return series
    for a in KNOWN_ASSETS:
        if a in tk:
            return a
    return "OTHER"


def _f(v: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if v is None or v == "":
            return default
        out = float(v)
        return out if math.isfinite(out) else default
    except (TypeError, ValueError):
        return default


def load_trades(user_id: int, days: int = 30) -> List[Dict[str, Any]]:
    """Load the user's resolvable, real (non-synthetic, non-void) closed trades from the last `days`."""
    days = max(1, min(int(days or 30), MAX_DAYS))
    cutoff = time.time() - days * 86400
    outcomes = _load_market_results()
    conn = get_db_connection()
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, ticker, side, entry_price, exit_price, count, pnl, status, mode, reason,
                   exit_reason, trading_style, signal_source, timestamp, settled_at, min_seen_bid, raw_json
            FROM trades
            WHERE user_id = ? AND status != 'OPEN'
            ORDER BY COALESCE(settled_at, 0) ASC, rowid ASC
            """,
            (int(user_id),),
        ).fetchall()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    out: List[Dict[str, Any]] = []
    for row in rows:
        t = dict(row)
        ticker = str(t.get("ticker") or "")
        if not ticker or "_SYNTH" in ticker.upper():
            continue
        status = str(t.get("status") or "").upper()
        exit_reason = str(t.get("exit_reason") or "")
        if "VOID" in status or "VOID" in exit_reason.upper():
            continue
        ts = _f(t.get("settled_at")) or _trade_epoch(t.get("timestamp"))
        if not ts or ts < cutoff:
            continue
        side = str(t.get("side") or "").upper()
        entry = _f(t.get("entry_price"))
        count = _f(t.get("count"), 0.0) or 0.0
        if side not in ("YES", "NO") or entry is None or not (0.0 < entry < 1.0) or count <= 0:
            continue
        exit_price = _f(t.get("exit_price"))

        outcome = outcomes.get(ticker)
        if outcome not in ("YES", "NO"):
            # Fall back to the trade's own settlement when it was held to expiry.
            if exit_reason.upper().startswith("SETTLE") and exit_price is not None:
                won = exit_price >= 0.5
                outcome = side if won else ("NO" if side == "YES" else "YES")
            else:
                outcome = None

        try:
            raw = json.loads(t.get("raw_json") or "{}")
            if not isinstance(raw, dict):
                raw = {}
        except ValueError:
            raw = {}

        prob = _f(raw.get("probability_percent"))
        out.append({
            "id": t.get("id"),
            "ticker": ticker,
            "asset": asset_from_ticker(ticker),
            "side": side,
            "entry": entry,
            "exit": exit_price,
            "count": count,
            "pnl": _f(t.get("pnl"), 0.0) or 0.0,
            "min_bid": _f(t.get("min_seen_bid")),
            "outcome": outcome,
            "ts": ts,
            "prob": prob,
            "model": str(raw.get("model_choice") or "UNKNOWN"),
            "style": str(t.get("trading_style") or "AUTO").upper(),
            "is_manual": bool(is_manual_entry(t)),
            "exit_reason": exit_reason,
            "held": exit_reason.upper().startswith("SETTLE"),
        })
    return out


_dip_cache: Dict[str, Any] = {"at": 0.0, "dds": []}


def _winner_drawdowns() -> List[float]:
    """Sorted max-adverse-excursion fractions (1 - min_bid/entry) of winning trades that were held all
    the way to settlement (so their full low is known), across all users over the last MAX_DAYS.
    Cached for 10 minutes."""
    if _dip_cache["dds"] and time.time() - _dip_cache["at"] < 600:
        return _dip_cache["dds"]
    outcomes = _load_market_results()
    cutoff = time.time() - MAX_DAYS * 86400
    dds: List[float] = []
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT ticker, side, entry_price, min_seen_bid, exit_reason FROM trades "
            "WHERE status != 'OPEN' AND COALESCE(settled_at, 0) >= ? AND min_seen_bid IS NOT NULL",
            (cutoff,),
        ).fetchall()
    finally:
        try:
            conn.close()
        except Exception:
            pass
    for ticker, side, entry, min_bid, exit_reason in rows:
        if not str(exit_reason or "").upper().startswith("SETTLE"):
            continue
        e, mb = _f(entry), _f(min_bid)
        if not e or mb is None or not (0 < e < 1) or outcomes.get(str(ticker)) != str(side or "").upper():
            continue
        dds.append(max(0.0, 1.0 - mb / e))
    dds.sort()
    _dip_cache.update(at=time.time(), dds=dds)
    return dds


def _dip_prob(sl_pct: float, dds: List[float]) -> float:
    """P(an eventual winner trades down by >= sl_pct before settling)."""
    import bisect
    if len(dds) < 15:
        return 0.35  # not enough fully-observed winners yet; neutral-pessimistic prior
    idx = bisect.bisect_left(dds, sl_pct / 100.0)
    return (len(dds) - idx) / len(dds)


def _simulate_trade(t: Dict[str, Any], tp_pct: float, sl_pct: float, tp_on: bool, sl_on: bool,
                    p_dip: float = 0.0):
    """Return (exit_price, exit_kind) for one trade under the given TP/SL settings.

    exit_price may be an expected value (kind 'ESTIMATED') when the trade closed early in reality and
    the post-exit path needed to decide between SL and TP is unknown."""
    e = t["entry"]
    won = t["outcome"] == t["side"]
    observed = [p for p in (t["min_bid"], t["exit"]) if p is not None]
    observed_low = min(observed) if observed else e
    observed_high = t["exit"] if t["exit"] is not None else e

    sl_price = max(0.0, e * (1.0 - sl_pct / 100.0))
    sl_fill = max(0.0, sl_price - STOP_SLIPPAGE)
    tp_price = e * (1.0 + tp_pct / 100.0)
    tp_reachable = tp_on and tp_price < 0.995

    if sl_on and observed_low <= sl_price:  # also covers "both touched" -> pessimistic SL-first
        return sl_fill, "STOP_LOSS"
    if tp_reachable and observed_high >= tp_price:
        return tp_price, "TAKE_PROFIT"
    if won:
        win_exit = tp_price if tp_reachable else 1.0
        win_kind = "TAKE_PROFIT" if tp_reachable else "SETTLE_WIN"
        if sl_on and not t.get("held") and p_dip > 0:
            return p_dip * sl_fill + (1.0 - p_dip) * win_exit, "ESTIMATED"
        return win_exit, win_kind
    return (sl_fill, "STOP_LOSS") if sl_on else (0.0, "SETTLE_LOSS")


def _stats(pnls: List[float]) -> Dict[str, Any]:
    n = len(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_w = sum(wins)
    gross_l = abs(sum(losses))
    cum = peak = dd = 0.0
    for p in pnls:
        cum += p
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    pf = (gross_w / gross_l) if gross_l > 0 else (99.0 if gross_w > 0 else 0.0)
    return {
        "trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / n * 100, 1) if n else 0.0,
        "net_pnl": round(sum(pnls), 2),
        "avg_pnl": round(sum(pnls) / n, 2) if n else 0.0,
        "avg_win": round(gross_w / len(wins), 2) if wins else 0.0,
        "avg_loss": round(gross_l / len(losses), 2) if losses else 0.0,
        "profit_factor": round(min(pf, 99.0), 2),
        "max_drawdown": round(dd, 2),
    }


def _curve(pnls: List[float], limit: int = 120) -> List[float]:
    cum, pts = 0.0, []
    for p in pnls:
        cum += p
        pts.append(round(cum, 2))
    if len(pts) > limit:
        step = len(pts) / limit
        pts = [pts[int(i * step)] for i in range(limit - 1)] + [pts[-1]]
    return pts


def _replay(trades: Iterable[Dict[str, Any]], tp_pct, sl_pct, tp_on, sl_on, use_kelly, size_dollars,
            dds: Optional[List[float]] = None):
    sim_pnls: List[float] = []
    act_pnls: List[float] = []
    kinds: Dict[str, int] = {}
    per_asset: Dict[str, List[float]] = {}
    kelly_skipped = 0
    p_dip = _dip_prob(sl_pct, dds or []) if sl_on else 0.0
    for t in trades:
        e = t["entry"]
        base = max(1, math.floor(size_dollars / e)) if size_dollars else t["count"]
        # Re-scale what really happened to the same base size so sim vs actual is like-for-like.
        actual = t["pnl"] * (base / t["count"]) if t["count"] else t["pnl"]
        act_pnls.append(actual)
        count = base
        if use_kelly:
            p_win = (t["prob"] / 100.0) if t["prob"] else 0.50
            if p_win <= e:
                kelly_skipped += 1
                continue
            frac = min(1.0, max(0.25, (p_win - e) / 0.15))
            count = max(1, int(count * frac))
        exit_px, kind = _simulate_trade(t, tp_pct, sl_pct, tp_on, sl_on, p_dip)
        pnl = (exit_px - e) * count
        sim_pnls.append(pnl)
        kinds[kind] = kinds.get(kind, 0) + 1
        per_asset.setdefault(t["asset"], []).append(pnl)
    return sim_pnls, act_pnls, kinds, per_asset, kelly_skipped


def run_backtest(
    user_id: int,
    *,
    days: int = 30,
    tp_pct: float = 20.0,
    sl_pct: float = 50.0,
    tp_enabled: bool = True,
    sl_enabled: bool = True,
    use_kelly: bool = False,
    model: str = "ALL",
    assets: Optional[List[str]] = None,
    include_manual: bool = False,
    trade_size_dollars: Optional[float] = None,
    optimize: bool = True,
) -> Dict[str, Any]:
    started = time.time()
    tp_pct = max(1.0, min(float(tp_pct or 0), 500.0))
    sl_pct = max(1.0, min(float(sl_pct or 0), 99.0))
    size = _f(trade_size_dollars)
    size = size if size and size > 0 else None

    all_trades = load_trades(user_id, days)
    models_available = sorted({t["model"] for t in all_trades})
    assets_available = sorted({t["asset"] for t in all_trades})

    wanted_assets = {a.upper() for a in (assets or []) if a}
    unresolved = 0
    pool: List[Dict[str, Any]] = []
    for t in all_trades:
        if not include_manual and t["is_manual"]:
            continue
        if model and model.upper() != "ALL" and t["model"].upper() != model.upper():
            continue
        if wanted_assets and t["asset"] not in wanted_assets:
            continue
        if t["outcome"] is None:
            unresolved += 1
            continue
        pool.append(t)

    dds = _winner_drawdowns()
    sim, act, kinds, per_asset, kelly_skipped = _replay(
        pool, tp_pct, sl_pct, tp_enabled, sl_enabled, use_kelly, size, dds)

    best = None
    if optimize and len(pool) >= 10:
        tp_grid = [(v, True) for v in range(10, 101, 10)] + [(0, False)]
        sl_grid = [(v, True) for v in range(10, 91, 10)] + [(0, False)]
        for tp_v, tp_on in tp_grid:
            for sl_v, sl_on in sl_grid:
                s, _, _, _, _ = _replay(pool, tp_v or 1, sl_v or 1, tp_on, sl_on, use_kelly, size, dds)
                net = sum(s)
                if best is None or net > best["net_pnl"]:
                    wr = (sum(1 for p in s if p > 0) / len(s) * 100) if s else 0.0
                    best = {"tp_pct": tp_v if tp_on else None, "sl_pct": sl_v if sl_on else None,
                            "net_pnl": round(net, 2), "win_rate": round(wr, 1), "trades": len(s)}

    by_asset = sorted(
        ({"asset": a, **_stats(p)} for a, p in per_asset.items()),
        key=lambda x: x["net_pnl"], reverse=True)

    return {
        "settings": {
            "days": max(1, min(int(days or 30), MAX_DAYS)), "tp_pct": tp_pct, "sl_pct": sl_pct,
            "tp_enabled": bool(tp_enabled), "sl_enabled": bool(sl_enabled), "use_kelly": bool(use_kelly),
            "model": model or "ALL", "assets": sorted(wanted_assets), "include_manual": bool(include_manual),
            "trade_size_dollars": size,
        },
        "simulated": _stats(sim),
        "actual": _stats(act),
        "improvement": round(sum(sim) - sum(act), 2),
        "exit_breakdown": kinds,
        "by_asset": by_asset,
        "equity_sim": _curve(sim),
        "equity_actual": _curve(act),
        "best": best,
        "kelly_skipped": kelly_skipped,
        "unresolved": unresolved,
        "sample_size": len(pool),
        "models_available": models_available,
        "assets_available": assets_available,
        "elapsed_ms": int((time.time() - started) * 1000),
    }

from backend.database.trade_store import TradeStore

def run_simulation(user_id: int, tp_pct: float, sl_pct: float) -> dict:
    trades = TradeStore.get_recent_trades(user_id, limit=500)
    simulated_net_pnl = 0.0
    wins = 0
    total = 0
    points = []
    
    tp_decimal = tp_pct / 100.0 if tp_pct > 0 else 0.0
    sl_decimal = sl_pct / 100.0 if sl_pct > 0 else 0.0

    # Sort trades ascending by timestamp if we want to simulate properly, get_recent_trades returns DESC by rowid.
    trades = list(reversed(trades))

    for t in trades:
        entry = t.get("entry_price")
        exit_p = t.get("exit_price")
        if not entry or not exit_p:
            continue
        
        entry = float(entry)
        exit_p = float(exit_p)
        count = float(t.get("count", 1))
        
        if entry <= 0:
            continue
            
        roi = (exit_p - entry) / entry
        side = t.get("side", "YES").upper()
        if side == "NO":
            roi = (entry - exit_p) / entry # Approximation
            
        is_win = False
        pnl = 0.0
        
        # Mock linear simulation
        if tp_decimal > 0 and roi >= tp_decimal:
            is_win = True
            pnl = entry * tp_decimal * count
        elif sl_decimal > 0 and roi <= -sl_decimal:
            is_win = False
            pnl = entry * -sl_decimal * count
        else:
            is_win = roi > 0
            pnl = entry * roi * count
            
        simulated_net_pnl += pnl
        if is_win:
            wins += 1
        total += 1
        
        points.append({
            "pnl": round(simulated_net_pnl, 2),
            "ts": t.get("timestamp") or t.get("settled_at") or 0
        })
        
    win_rate = (wins / total * 100) if total > 0 else 0.0
    return {
        "net_pnl": round(simulated_net_pnl, 2),
        "win_rate": round(win_rate, 2),
        "points": points
    }
