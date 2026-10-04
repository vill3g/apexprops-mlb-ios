"""
TP/SL Optimizer — brute-force simulation across a grid of TP% and SL%
values to find the mathematically best settings for each user based on
their real closed-trade history.

Usage:
    from backend.btc.tpsl_optimizer import get_recommended_tpsl
    rec = get_recommended_tpsl(user_id=4)
"""
import logging
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Cache: { user_id -> (timestamp, result_dict_or_None) }
_tpsl_cache: Dict[int, tuple] = {}
_CACHE_TTL = 30 * 60  # 30 minutes

# Simulation grid
_TP_RANGE = [pct for pct in range(5, 205, 5)]   # 5% to 200% step 5
_SL_RANGE = [pct for pct in range(5, 85, 5)]    # 5% to 80% step 5
_MIN_TRADES = 10


def _simulate(trades, tp_pct: float, sl_pct: float):
    """
    Replay each closed trade against the given (tp_pct, sl_pct) pair and
    compute simulated PnL and win-rate.

    Trade fields used:
        side        : "YES" or "NO"
        entry_price : float 0-1
        exit_price  : float 0-1
        pnl         : actual realised PnL ($) — used to scale simulated PnL

    Logic:
        For YES trades, a win means exit_price > entry_price.
            gain_pct = (exit_price - entry_price) / entry_price * 100
            loss_pct = (entry_price - exit_price) / entry_price * 100
        For NO  trades, a win means exit_price < entry_price.
            gain_pct = (entry_price - exit_price) / entry_price * 100
            loss_pct = (exit_price - entry_price) / entry_price * 100

        If gain_pct >= tp_pct  → simulated TP hit  (count as win)
        If loss_pct >= sl_pct  → simulated SL hit  (count as loss)
        Otherwise              → use actual outcome
    """
    wins = 0
    net_pnl = 0.0
    total = 0

    for t in trades:
        entry = float(t.get("entry_price") or 0.0)
        exit_p = float(t.get("exit_price") or 0.0)
        actual_pnl = float(t.get("pnl") or 0.0)
        side = str(t.get("side") or "YES").upper()

        if entry <= 0 or exit_p <= 0:
            # Not enough info — skip
            continue

        total += 1

        if side == "YES":
            gain_pct = (exit_p - entry) / entry * 100.0
            loss_pct = (entry - exit_p) / entry * 100.0
        else:
            gain_pct = (entry - exit_p) / entry * 100.0
            loss_pct = (exit_p - entry) / entry * 100.0

        if gain_pct >= tp_pct:
            # TP triggered — use actual win magnitude scaled by tp ratio
            scale = min(tp_pct / max(gain_pct, 0.01), 1.0)
            sim_pnl = abs(actual_pnl) * scale if actual_pnl > 0 else abs(actual_pnl) * 0.5 * scale
            wins += 1
            net_pnl += sim_pnl
        elif loss_pct >= sl_pct:
            # SL triggered — cut the loss at the SL level
            scale = min(sl_pct / max(loss_pct, 0.01), 1.0)
            sim_pnl = -(abs(actual_pnl) * scale) if actual_pnl < 0 else -(abs(actual_pnl) * 0.5 * scale)
            net_pnl += sim_pnl
        else:
            # Neither hit — use actual outcome
            if actual_pnl > 0:
                wins += 1
            net_pnl += actual_pnl

    return total, wins, net_pnl


def get_recommended_tpsl(user_id: int) -> Optional[dict]:
    """
    Return the best (TP%, SL%) pair for *user_id* based on their closed
    trade history, or None if fewer than 10 closed trades exist.

    Result is cached per user for 30 minutes.

    Returns a dict:
        {
            "recommended_tp": float,
            "recommended_sl": float,
            "win_rate":       float,   # 0.0-1.0
            "net_pnl":        float,
            "sample_size":    int,
        }
    """
    now = time.time()
    cached = _tpsl_cache.get(user_id)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]

    try:
        from backend.database.trade_store import TradeStore

        # Fetch up to 200 recent closed trades
        raw_trades = TradeStore.get_recent_trades(user_id, limit=200)
        closed = [t for t in raw_trades if str(t.get("status", "")).upper() != "OPEN"]

        if len(closed) < _MIN_TRADES:
            _tpsl_cache[user_id] = (now, None)
            return None

        best_tp = None
        best_sl = None
        best_pnl = None
        best_wr = None
        best_sample = len(closed)

        for tp_pct in _TP_RANGE:
            for sl_pct in _SL_RANGE:
                total, wins, net_pnl = _simulate(closed, tp_pct, sl_pct)
                if total == 0:
                    continue
                win_rate = wins / total
                if win_rate < 0.5:
                    continue  # Require at least 50% win-rate
                if best_pnl is None or net_pnl > best_pnl:
                    best_pnl = net_pnl
                    best_tp = tp_pct
                    best_sl = sl_pct
                    best_wr = win_rate
                    best_sample = total

        if best_tp is None:
            # Relax win-rate constraint — find best net PnL unconditionally
            for tp_pct in _TP_RANGE:
                for sl_pct in _SL_RANGE:
                    total, wins, net_pnl = _simulate(closed, tp_pct, sl_pct)
                    if total == 0:
                        continue
                    win_rate = wins / total
                    if best_pnl is None or net_pnl > best_pnl:
                        best_pnl = net_pnl
                        best_tp = tp_pct
                        best_sl = sl_pct
                        best_wr = win_rate
                        best_sample = total

        if best_tp is None:
            _tpsl_cache[user_id] = (now, None)
            return None

        result = {
            "recommended_tp": float(best_tp),
            "recommended_sl": float(best_sl),
            "win_rate": round(best_wr, 4),
            "net_pnl": round(best_pnl, 2),
            "sample_size": best_sample,
        }
        _tpsl_cache[user_id] = (now, result)
        return result

    except Exception as e:
        logger.warning(f"tpsl_optimizer error for user {user_id}: {e}")
        _tpsl_cache[user_id] = (now, None)
        return None
