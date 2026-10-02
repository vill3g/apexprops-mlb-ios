"""
Unified Data Access Layer: User Trade Repository
Encapsulates thread safety, JSON persistence, and startup reconciliation
for multi-tenant user trade histories.
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from backend.btc.io_utils import atomic_json_write
from backend.database.models import (DATA_DIR, credit_user_paper_balance,
                                     get_user_lock)

logger = logging.getLogger(__name__)


def _get_user_trades_path(user_id: Any) -> str:
    """Resolve the absolute path to a user's trades_history.json file."""
    return os.path.join(DATA_DIR, "users", str(user_id), "trades_history.json")


def get_user_trades(user_id: Any) -> List[Dict[str, Any]]:
    """
    Safely retrieve a user's full trade history under their user lock.
    Returns an empty list if the file does not exist or is corrupted.
    """
    path = _get_user_trades_path(user_id)
    with get_user_lock(user_id):
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning(f"[TradeRepo] Failed to read trades for user {user_id}: {e}")
            return []


def save_user_trades(user_id: Any, trades: List[Dict[str, Any]]) -> None:
    """
    Atomically save a user's trade history under their user lock.
    """
    path = _get_user_trades_path(user_id)
    with get_user_lock(user_id):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            atomic_json_write(path, trades)
        except Exception as e:
            logger.error(f"[TradeRepo] Failed to save trades for user {user_id}: {e}")
            raise e


def add_user_trade(user_id: Any, trade: Dict[str, Any]) -> None:
    """
    Append a single trade record to the user's history under lock.
    """
    with get_user_lock(user_id):
        trades = get_user_trades(user_id)
        trades.append(trade)
        save_user_trades(user_id, trades)


def get_user_open_trades(user_id: Any) -> List[Dict[str, Any]]:
    """
    Retrieve all currently OPEN trades for a given user.
    """
    trades = get_user_trades(user_id)
    return [t for t in trades if t.get("status") == "OPEN"]


def parse_trade_epoch(timestamp_val: Any) -> float:
    """Convert various timestamp formats into a Unix epoch timestamp."""
    if isinstance(timestamp_val, (int, float)):
        return float(timestamp_val)
    if isinstance(timestamp_val, str):
        try:
            if "ET" in timestamp_val:
                # "2026-09-27 02:45:03 PM ET": the AM/PM marker matters (it was dropped, so
                # afternoon trades looked 12 hours old and were closed with a guessed result)
                clean_ts = timestamp_val.replace(" ET", "").strip()
                try:
                    dt = datetime.strptime(clean_ts, "%Y-%m-%d %I:%M:%S %p")
                except ValueError:
                    dt = datetime.strptime(clean_ts[:19], "%Y-%m-%d %H:%M:%S")
                return dt.replace(tzinfo=ZoneInfo("America/New_York")).timestamp()
            else:
                dt = datetime.fromisoformat(timestamp_val.replace("Z", "+00:00"))
                return dt.timestamp()
        except Exception as e:
            logger.warning(f"Error parsing trade epoch: {e}")
            return 0.0
    return 0.0


def reconcile_expired_open_trades() -> int:
    """
    Startup Self-Healing Reconciler:
    Scans all registered user trade history files at application boot.
    Finds trades stuck in 'OPEN' status whose 15-minute contract duration has
    expired, queries the Kalshi API or candle close for settlement resolution,
    finalizes their status to 'CLOSED' (SETTLEMENT), and credits user balances if won.
    Returns the number of resolved zombie trades.
    """
    users_dir = os.path.join(DATA_DIR, "users")
    if not os.path.isdir(users_dir):
        return 0

    reconciled_count = 0
    now = time.time()
    # Contract is 15 minutes; allow 5 min buffer -> 20 minutes (1200s)
    EXPIRATION_THRESHOLD_SECONDS = 1200.0

    try:
        from backend.btc.kalshi_trader import kalshi_trader
    except ImportError:
        kalshi_trader = None

    for uid in os.listdir(users_dir):
        user_path = os.path.join(users_dir, uid, "trades_history.json")
        if not os.path.isfile(user_path):
            continue

        try:
            with get_user_lock(uid):
                with open(user_path, "r", encoding="utf-8") as f:
                    trades = json.load(f)

                modified = False
                for t in trades:
                    if t.get("status") != "OPEN":
                        continue

                    trade_epoch = parse_trade_epoch(t.get("timestamp"))
                    trade_age = (now - trade_epoch) if trade_epoch > 0 else 99999.0

                    if trade_age < EXPIRATION_THRESHOLD_SECONDS:
                        continue  # Still currently active or in legitimate window

                    ticker = t.get("ticker", "")
                    try:
                        from backend.btc.market_results import \
                            market_close_epoch
                        close_ts = market_close_epoch(ticker)
                    except Exception as e:
                        logger.warning(f"Error fetching market close epoch for {ticker}: {e}")
                        close_ts = None
                    if close_ts is not None and now < close_ts:
                        continue  # the market is still open: leave it to stop-loss / take-profit / settlement
                    side = str(t.get("side") or t.get("direction") or "YES").upper()
                    count = int(t.get("count", 1))
                    entry = float(t.get("entry_price", 0.50))
                    mode = t.get("mode", "PAPER")

                    exit_price = 0.0
                    resolved = False

                    # Attempt official Kalshi resolution
                    if kalshi_trader and ticker and "SYNTH" not in ticker.upper():
                        try:
                            res = kalshi_trader.get_market_result(ticker)
                            ans = str(res.get("result", "")).lower()
                            if ans in ("yes", "no"):
                                exit_price = 1.0 if side == ans.upper() else 0.0
                                resolved = True
                        except Exception as _e:
                            logger.debug(f"[StartupReconciler] Kalshi query failed for {ticker}: {_e}")

                    # Never guess a result from the model's probability (it used to call anything
                    # >= 55% a win). A placeholder market that never existed on Kalshi is voided.
                    void = not resolved and "SYNTH" in ticker.upper()
                    if void:
                        exit_price = entry          # refund: no profit, no loss
                        resolved = True

                    if resolved:
                        from backend.btc.fees import net_pnl
                        t["status"] = "CLOSED"
                        t["exit_reason"] = "VOID_PLACEHOLDER_MARKET" if void else "SETTLEMENT"
                        t["exit_price"] = exit_price
                        t["settled_at"] = now
                        t["reconciled_at_startup"] = True
                        t["pnl"] = 0.0 if void else net_pnl(entry, exit_price, count)
                        modified = True
                        reconciled_count += 1

                        if mode == "PAPER" and exit_price > 0:
                            payout = count * exit_price
                            try:
                                credit_user_paper_balance(int(uid), payout)
                                logger.info(f"[StartupReconciler] Credited User #{uid} +${payout:.2f} for won position {ticker}")
                            except Exception as _cb_err:
                                logger.warning(f"[StartupReconciler] Balance credit failed: {_cb_err}")

                        logger.info(f"[StartupReconciler] Reconciled expired trade {t.get('id')} ({ticker}) -> PnL: ${t['pnl']:.2f}")

                if modified:
                    atomic_json_write(user_path, trades)

        except Exception as e:
            logger.warning(f"[StartupReconciler] Failed reconciling user {uid}: {e}")

    if reconciled_count > 0:
        logger.info(f"[StartupReconciler] Successfully self-healed {reconciled_count} expired open trades.")
    return reconciled_count
