from backend.btc.data_fetcher import get_candle_countdown
import logging
import threading

# The real _history_lock (cross-process) comes from .shared via `from .shared import *` below.

logger = logging.getLogger(__name__)

def _run_historical_training(data_dir, ml_style, asset, effective_style):
    import logging
    from backend.btc.data_fetcher import fetch_15m_candles_history, fetch_1m_candles_history
    from backend.btc.indicators import add_all_indicators
    from backend.btc.ml_engine import get_ml_engine
    try:
        if effective_style == "MOMENTUM_SURFER":
            hist_df = fetch_1m_candles_history(days=15)
        else:
            hist_df = fetch_15m_candles_history(days=60)
        hist_df_ind = add_all_indicators(hist_df)
        engine = get_ml_engine(data_dir, trading_style=ml_style, asset=asset)
        engine.self_train_on_historical_market(hist_df_ind)
    except Exception as e:
        logging.error(f"[_run_historical_training] failed: {e}")

import copy
import json
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    pass
import sqlite3

import requests

from backend.btc.analyzer.contract_eval import evaluate_next_15m_contract
from backend.btc.chop_engine import evaluate_chop_contract
from backend.btc.data_fetcher import (fetch_1m_candles_history,
                                      fetch_15m_candles_history,
                                      get_live_15m_target_data)
from backend.btc.fees import kalshi_order_fee
from backend.btc.indicators import add_all_indicators
from backend.btc.io_utils import atomic_json_write as _atomic_json_write
from backend.btc.kalshi_trader import kalshi_trader
from backend.btc.loss_analyzer import loss_analyzer
from backend.btc.ml_engine import get_ml_engine
from backend.btc.paper_balance import load_balance, update_balance
from backend.btc.pattern_detector import detect_candlestick_patterns
from backend.btc.scalp_engine import scalp_engine
from backend.btc.shadow_executor import execute_shadow_trade
from backend.btc.trade_db import get_trade_db
from backend.database import order_intents
from backend.engine.multi_asset_fetcher import \
    fetch_asset_candles as fetch_candles
from backend.engine.multi_asset_fetcher import \
    get_asset_ticker as get_btc_ticker
from backend.engine.multi_asset_fetcher import (
                                                is_market_open)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data")
HISTORY_FILE = os.path.join(DATA_DIR, "trades_history.json")
CONFIG_FILE = os.path.join(DATA_DIR, "trading_config.json")
from .risk_manager import RiskManagerMixin
from .saas_broadcaster import SaasBroadcasterMixin
from .settlement import SettlementMixin
from .shared import _history_lock, classify_auto_regime
from .stop_manager import StopManagerMixin


def normalize_prediction_direction(value: Any) -> str:
    """Map analyzer and recommendation labels to the two Kalshi outcomes."""
    label = str(value or "").upper().strip()
    if not label:
        return "PASS"
    # Explicitly check for action keywords first so CHOP FADE trades execute
    if "BID YES" in label or "ABOVE" in label or label in {"YES", "UP"}:
        return "ABOVE"
    if "BID NO" in label or "BELOW" in label or label in {"NO", "DOWN"}:
        return "BELOW"
    if "PASS" in label or "CHOP" in label:
        return "PASS"
    return "PASS"




class AutoExecutor(SaasBroadcasterMixin, RiskManagerMixin, StopManagerMixin, SettlementMixin):
        def __init__(self, asset: str = "BTC"):
            self.asset = asset
            self.enabled: bool = False
            self.mode: str = "PAPER"  # "PAPER" or "LIVE"
            self.min_conviction: str = "GRADE B SETUP"  # "GRADE A+ SETUP", "GRADE A SETUP", or "GRADE B SETUP"
            self.max_contracts: int = 1
            self.prediction_mode: bool = True
            self.broadcast_trades: bool = True
            self.max_daily_risk: float = 25.0
            self.max_daily_trades: int = 10
            self.last_traded_interval: Optional[str] = None
            self.last_check_time: float = 0.0
            self.ai_settings: dict = {}
            self._rollover_lock = threading.Lock()
            self._saas_eval_lock = threading.Lock()
            self._config_lock = threading.Lock()
            self._last_saas_eval_time: float = 0.0
            # Instance-level trade cache (not class-level, to avoid cross-instance contamination)
            self._cached_trades: List[Dict[str, Any]] = []
            self._cached_trades_mtime: float = 0.0
            self._settled_since_drift_check: int = 0
    
            # Per-asset config and history paths — BTC keeps legacy filenames for backward compatibility
            asset_suffix = "" if asset == "BTC" else f"_{asset}"
            self._config_file = os.path.join(DATA_DIR, f"trading_config{asset_suffix}.json")
            self._history_file = os.path.join(DATA_DIR, f"trades_history{asset_suffix}.json")
    
            os.makedirs(DATA_DIR, exist_ok=True)
            try:
                self.trade_db = get_trade_db()
                self.trade_db.import_from_json_if_needed(self._history_file, asset=self.asset)
            except sqlite3.OperationalError as dbe:
                logger.warning(f"[AutoExecutor] TradeDB init error: {dbe}")
                self.trade_db = None
    
            self._load_config()

        def set_ai_settings(self, data: dict):
            self.ai_settings = data
            self.ai_settings.pop("maxEntryPriceDollars", None)
            self._save_config()
            return {"status": "ok"}

        def _load_config(self):
            with getattr(self, "_config_lock", __import__("contextlib").nullcontext()):
                if os.path.exists(self._config_file):
                    try:
                        with open(self._config_file, "r", encoding="utf-8") as f:
                            cfg = json.load(f)
                            self.enabled = bool(cfg.get("enabled", False))
                            self.mode = cfg.get("mode", "PAPER")
                            self.min_conviction = cfg.get("min_conviction", "GRADE B SETUP")
                            self.max_contracts = int(cfg.get("max_contracts", 1))
                            self.prediction_mode = bool(cfg.get("prediction_mode", True))
                            self.broadcast_trades = bool(cfg.get("broadcast_trades", True))
                            self.max_daily_risk = float(cfg.get("max_daily_risk", 25.0))
                            self.max_daily_trades = int(cfg.get("max_daily_trades", 10))
                            self.ai_settings = cfg.get("ai_settings") or {}
                            if not isinstance(self.ai_settings, dict):
                                self.ai_settings = {}
                            if self.mode == "LIVE":
                                self.ai_settings["dryRun"] = False
                            elif "dryRun" not in self.ai_settings:
                                self.ai_settings["dryRun"] = (self.mode == "PAPER")
                            if "ignorePass" not in self.ai_settings:
                                self.ai_settings["ignorePass"] = False
                            if "dynamicStopLoss" not in self.ai_settings:
                                self.ai_settings["dynamicStopLoss"] = True
                            if "stopLossMoveDollars" not in self.ai_settings:
                                self.ai_settings["stopLossMoveDollars"] = 45.0
                            if "stopLossMaxMinutes" not in self.ai_settings:
                                self.ai_settings["stopLossMaxMinutes"] = 8.0
                            if "positionReversal" not in self.ai_settings:
                                self.ai_settings["positionReversal"] = False
                            if "reversalMaxPriceCents" not in self.ai_settings:
                                self.ai_settings["reversalMaxPriceCents"] = 65.0
                            if "reversalMinMinutesLeft" not in self.ai_settings:
                                self.ai_settings["reversalMinMinutesLeft"] = 6.0
                            if "reversalMinConfidence" not in self.ai_settings:
                                self.ai_settings["reversalMinConfidence"] = 75.0
                            if "slippageBufferDollars" not in self.ai_settings:
                                if "slippageBufferCents" in self.ai_settings:
                                    self.ai_settings["slippageBufferDollars"] = self.ai_settings.pop("slippageBufferCents")
                                else:
                                    self.ai_settings["slippageBufferDollars"] = 0.04
                            self.ai_settings.pop("maxEntryPriceDollars", None)
                            if "oneShotAiStartTrade" not in self.ai_settings:
                                self.ai_settings["oneShotAiStartTrade"] = False
                            if "useKellyCriterion" not in self.ai_settings:
                                self.ai_settings["useKellyCriterion"] = False
                            if "use_kelly_criterion" not in self.ai_settings:
                                self.ai_settings["use_kelly_criterion"] = False
                            # Finding 1: Startup safety override
                            if self.mode == "LIVE" and not os.path.exists(self._history_file):
                                logger.warning(
                                    f"[AutoExecutor] SAFETY OVERRIDE: Deployment has mode=LIVE but no trades history found for {self.asset}. "
                                    "Demoting mode to 'PAPER' and setting enabled=False for safety."
                                )
                                self.mode = "PAPER"
                                self.enabled = False
                                self._save_config()
                    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
                        logger.error(f"[AutoExecutor] Error loading config: {e}")

        def _save_config(self):
            with getattr(self, "_config_lock", __import__("contextlib").nullcontext()):
                try:
                    _atomic_json_write(self._config_file, {
                        "enabled": self.enabled,
                        "mode": self.mode,
                        "min_conviction": self.min_conviction,
                        "max_contracts": self.max_contracts,
                        "prediction_mode": self.prediction_mode,
                        "broadcast_trades": getattr(self, "broadcast_trades", True),
                        "max_daily_risk": getattr(self, "max_daily_risk", 25.0),
                        "max_daily_trades": getattr(self, "max_daily_trades", 10),
                        "ai_settings": getattr(self, "ai_settings", {})
                    })
                except (OSError, IOError, ValueError, TypeError) as e:
                    logger.error(f"[AutoExecutor] Error saving config: {e}")

        def get_trades_history(self) -> List[Dict[str, Any]]:
            user_id = getattr(self, "user_id", None)
            if user_id is not None:
                try:
                    from backend.database.trade_store import TradeStore
                    return TradeStore.get_recent_trades(user_id, limit=50)
                except Exception as e:
                    logger.warning(f"[AutoExecutor] TradeStore error: {e}")
            try:
                with _history_lock:
                    if hasattr(self, "_history_file") and os.path.exists(self._history_file):
                        mtime = os.path.getmtime(self._history_file)
                        if mtime == getattr(self, "_cached_trades_mtime", 0.0) and getattr(self, "_cached_trades", None):
                            return list(self._cached_trades)
                        with open(self._history_file, 'r') as f:
                            trades = json.load(f)
                            self._cached_trades = trades
                            self._cached_trades_mtime = mtime
                            return list(trades)
            except Exception as e:
                logger.error(f"[AutoExecutor] Error loading trades: {e}")
            return []
        def _read_history_from_disk(self) -> List[Dict[str, Any]]:
            """The history file as it is on disk right now (no cache)."""
            try:
                if hasattr(self, "_history_file") and os.path.exists(self._history_file):
                    with open(self._history_file, 'r') as f:
                        data = json.load(f)
                        return data if isinstance(data, list) else []
            except (OSError, ValueError) as e:
                logger.error(f"[AutoExecutor] Could not re-read trade history before saving: {e}")
            return []

        @staticmethod
        def _merge_with_disk(ours: List[Dict[str, Any]], disk: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            """Audit H4: the web server and the worker both save this file, often from a list
            they read a while earlier. Saving that stale list verbatim used to drop trades the
            other process had just added, or flip a trade it had just settled back to OPEN (so
            it was settled - and paid - again). Merge instead:
              * a trade that is closed/settled on disk is never reverted to OPEN;
              * trades that exist only on disk (added by the other process) are kept."""
            disk_by_id = {t.get("id"): t for t in disk if isinstance(t, dict) and t.get("id")}
            our_ids = set()
            merged = []
            for t in ours:
                tid = t.get("id") if isinstance(t, dict) else None
                if tid:
                    our_ids.add(tid)
                    d = disk_by_id.get(tid)
                    if d is not None and str(d.get("status", "OPEN")).upper() != "OPEN" \
                            and str(t.get("status", "OPEN")).upper() == "OPEN":
                        merged.append(d)
                        continue
                merged.append(t)
            for d in disk:
                tid = d.get("id") if isinstance(d, dict) else None
                if tid and tid not in our_ids:
                    merged.append(d)
            return merged

        def _save_trades_history(self, trades: List[Dict[str, Any]]):
            try:
                with _history_lock:
                    # Merge with what's on disk now (the other process may have written since
                    # `trades` was read) and hand the merged list back to the caller.
                    trades[:] = self._merge_with_disk(list(trades), self._read_history_from_disk())
                    trade_db = getattr(self, "trade_db", None)
                    if trade_db is not None:
                        try:
                            trade_db.upsert_trades(trades, asset=self.asset)
                        except sqlite3.OperationalError as dbe:
                            logger.error(f"[AutoExecutor] TradeDB upsert error: {dbe}")
    
                    _atomic_json_write(self._history_file, trades)
                    self._cached_trades = trades
                    self._cached_trades_mtime = os.path.getmtime(self._history_file)
            except (OSError, IOError, ValueError, TypeError) as e:
                logger.error(f"[AutoExecutor] Error saving trades: {e}")

        def set_enabled(self, enabled: bool) -> Dict[str, Any]:
            self.enabled = enabled
            self._save_config()
            return {"status": "ok", "enabled": self.enabled, "mode": self.mode}

        def set_mode(self, mode: str) -> Dict[str, Any]:
            mode_clean = mode.upper().strip()
            if mode_clean in ["PAPER", "LIVE"]:
                if mode_clean == "LIVE":
                    if not kalshi_trader.is_authenticated():
                        return {"status": "error", "message": "Kalshi authentication required before switching to LIVE trading."}
                self.mode = mode_clean
                self._save_config()
                return {"status": "ok", "mode": self.mode}
            return {"status": "error", "message": f"Invalid mode {mode}. Choose PAPER or LIVE."}

        def set_conviction_threshold(self, threshold: str) -> Dict[str, Any]:
            clean = threshold.upper().strip()
            if "A+" in clean:
                self.min_conviction = "GRADE A+ SETUP"
            elif "B+" in clean:
                self.min_conviction = "GRADE B+ SETUP"
            elif "B" in clean:
                self.min_conviction = "GRADE B SETUP"
            else:
                self.min_conviction = "GRADE A SETUP"
            self._save_config()
            return {"status": "ok", "min_conviction": self.min_conviction}

        def set_max_contracts(self, count: int) -> Dict[str, Any]:
            # FIX #10: We removed the ABSOLUTE_MAX_CONTRACTS clamp at user request
            c = max(1, int(count))
            self.max_contracts = c
            self._save_config()
            return {"status": "ok", "max_contracts": self.max_contracts}

        def set_risk_limits(self, max_daily_risk: Optional[float] = None, max_daily_trades: Optional[int] = None) -> Dict[str, Any]:
            if max_daily_risk is not None:
                self.max_daily_risk = max(1.0, round(float(max_daily_risk), 2))
            if max_daily_trades is not None:
                self.max_daily_trades = max(1, int(max_daily_trades))
            self._save_config()
            return {
                "status": "ok",
                "max_daily_risk": self.max_daily_risk,
                "max_daily_trades": self.max_daily_trades,
                        "ai_settings": self.ai_settings
            }

        def get_status(self) -> Dict[str, Any]:
            """
            Returns full real-time trading console stats including live balance,
            win/loss rate, open trades, and current market info.
            """
            balance_info = kalshi_trader.get_balance()
            trades = self.get_trades_history()
    
            # Update settlement for prior trades
            self.check_settlements(trades)
            prediction_accuracy = self.get_prediction_accuracy(trades)
    
            # Filter stats by the current mode (PAPER or LIVE)
            mode_trades = [t for t in trades if t.get("mode", self.mode).upper() == self.mode]
            total_trades = len(mode_trades)
            wins = sum(1 for t in mode_trades if "WIN" in str(t.get("result", "")).upper())
            losses = sum(1 for t in mode_trades if "LOSS" in str(t.get("result", "")).upper())
            open_trades = [t for t in mode_trades if t.get("status") == "OPEN"]
    
            # Reconcile LIVE open trades against Kalshi portfolio to prevent ghost open positions
            if self.mode == "LIVE" and open_trades and kalshi_trader.is_authenticated():
                try:
                    pos_res = kalshi_trader.get_positions()
                    if pos_res.get("success"):
                        pos_list = pos_res.get("positions", [])
                        kalshi_pos_map = {p.get("ticker"): float(p.get("position_fp", 0.0) or 0.0) for p in pos_list}
                        reconciled_any = False
                        for t in list(open_trades):
                            ticker = t.get("ticker")
    
                            # Skip expired markets — settlement loop handles those
                            close_epoch = float(t.get("close_epoch") or float("inf"))
                            now_ts = time.time()
                            if now_ts > close_epoch:
                                continue
    
                            # Grace period: Kalshi's read-replica can lag up to 30s after order placement.
                            # Parse the trade timestamp directly to measure true age.
                            trade_age_seconds = 999.0  # default: old enough to reconcile
                            ts_str = t.get("timestamp", "")
                            if ts_str:
                                try:
                                    trade_dt = datetime.strptime(ts_str, "%Y-%m-%d %I:%M:%S %p ET").replace(tzinfo=ZoneInfo("America/New_York"))
                                    trade_age_seconds = now_ts - trade_dt.timestamp()
                                except Exception as e:
                                    logger.error(f"Timestamp parse failed for {ts_str}: {e}")
                                    trade_age_seconds = 999.0
    
                            # Do NOT reconcile trades younger than 60 seconds — give Kalshi API time to catch up
                            if trade_age_seconds < 60.0:
                                logger.debug(f"[AutoExecutor] Skipping reconcile for {t.get('id')} — trade is only {trade_age_seconds:.0f}s old (grace period active).")
                                continue
    
                            # Kalshi NO positions are reported as NEGATIVE position_fp — use abs() to detect flat correctly
                            val = kalshi_pos_map.get(ticker, 0.0)
                            is_sim = str(t.get("id", "")).startswith("sim_")
                            if abs(val) <= 0.001 and not is_sim:
                                logger.info(f"[AutoExecutor] Auto-reconciled flat Kalshi position for trade {t.get('id')} ({ticker}). Age={trade_age_seconds:.0f}s, position_fp={val}")
                                t["status"] = "CLOSED"
                                t["result"] = "CLOSED_FLAT"
                                t["exit_reason"] = "KALSHI_POSITION_RECONCILED"
                                t["closed_at"] = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET")
                                reconciled_any = True
                        if reconciled_any:
                            self._save_trades_history(trades)
                            open_trades = [t for t in mode_trades if t.get("status") == "OPEN"]
                except (requests.exceptions.RequestException, ValueError, TypeError, KeyError) as pos_err:
                    logger.debug(f"[AutoExecutor] Live position check skipped: {pos_err}")
    
            total_pnl = sum(float(t.get("pnl", 0.0)) for t in mode_trades)
            win_rate = round((wins / max(1, wins + losses)) * 100.0, 1) if (wins + losses) > 0 else 0.0
    
            # Calculate daily ET statistics
    #         from zoneinfo import ZoneInfo
            today_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
            today_trades = [
                t for t in mode_trades
                if str(t.get("timestamp", "")).startswith(today_str)
            ]
            today_trade_count = len(today_trades)
            today_realized_pnl, today_open_collateral, today_effective_risk = self._compute_effective_daily_risk(today_trades)
    
            active_market = kalshi_trader.get_active_15m_market(series_ticker=f"KX{self.asset}15M", force_refresh=True)
    
            # Compute live unrealized (mark-to-market) P&L for each open trade.
            # FIX #1: Work on deep copies so we never mutate the shared _cached_trades objects
            # without holding _history_lock (background settlement loop touches those dicts too).
            open_pnl_dollars = 0.0
            annotated_open_trades = []
            if active_market and open_trades:
                am_ticker = active_market.get("ticker")
                am_yes_bid = float(active_market.get("yes_bid") or 0.0)
                am_no_bid  = float(active_market.get("no_bid")  or 0.0)
                for t in open_trades:
                    t_copy = copy.deepcopy(t)  # deepcopy to prevent race conditions
                    side = str(t_copy.get("side", "YES")).upper()
                    entry = float(t_copy.get("entry_price", 0.5))
                    count = int(t_copy.get("count", 1))
                    
                    # Only use live market data if the trade belongs to the current active market.
                    # If it's an older expired trade awaiting settlement, fallback to its max_seen_bid or entry.
                    if t_copy.get("ticker") == am_ticker:
                        current_bid = am_yes_bid if side == "YES" else am_no_bid
                    else:
                        current_bid = float(t_copy.get("max_seen_bid", entry))
                    
                    live_pnl = round((current_bid - entry) * count, 4) if current_bid > 0 else 0.0
                    t_copy["live_pnl"] = live_pnl
                    t_copy["current_bid"] = current_bid
                    open_pnl_dollars += live_pnl
                    annotated_open_trades.append(t_copy)
            else:
                for t in open_trades:
                    t_copy = copy.deepcopy(t)
                    side = str(t_copy.get("side", "YES")).upper()
                    entry = float(t_copy.get("entry_price", 0.5))
                    count = int(t_copy.get("count", 1))
                    current_bid = float(t_copy.get("max_seen_bid", entry))
                    live_pnl = round((current_bid - entry) * count, 4)
                    t_copy["live_pnl"] = live_pnl
                    t_copy["current_bid"] = current_bid
                    open_pnl_dollars += live_pnl
                    annotated_open_trades.append(t_copy)
    
            # Paper Trading Balance Logic
            if self.mode == "PAPER":
                try:
                    bal_dollars = load_balance(guest_id=getattr(self, '_guest_id', None))
                except ImportError:
                    paper_start = 500.0
                    realized_pnl = sum(float(t.get("pnl", 0.0)) for t in trades if t.get("mode", "PAPER").upper() == "PAPER" and t.get("status") in ["SETTLED", "CLOSED"])
                    open_cost = sum(float(t.get("cost", 0.0)) for t in trades if t.get("mode", "PAPER").upper() == "PAPER" and t.get("status") == "OPEN")
                    bal_dollars = paper_start + realized_pnl - open_cost
                bal_cents = int(bal_dollars * 100)
                balance_info["balance_dollars"] = bal_dollars
                balance_info["balance_cents"] = bal_cents
    
            # Detect if autonomous execution is currently paused by risk limits
            is_risk_paused = False
            pause_reason = ""
            if self.enabled:
                if today_trade_count >= self.max_daily_trades:
                    is_risk_paused = True
                    pause_reason = f"Daily trade limit reached ({today_trade_count}/{self.max_daily_trades})"
                elif today_effective_risk <= -abs(self.max_daily_risk):
                    is_risk_paused = True
                    pause_reason = (
                        f"Daily loss limit reached (Settled: ${today_realized_pnl:.2f}, "
                        f"Open Collateral: ${today_open_collateral:.2f}, Effective: ${today_effective_risk:.2f} "
                        f"<= -${self.max_daily_risk:.2f})"
                    )
    
            return {
                "enabled": self.enabled,
                "is_risk_paused": is_risk_paused,
                "pause_reason": pause_reason,
                "mode": self.mode,
                "min_conviction": self.min_conviction,
                "max_contracts": self.max_contracts,
                "prediction_mode": self.prediction_mode,
                "max_daily_risk": self.max_daily_risk,
                "max_daily_trades": self.max_daily_trades,
                "ai_settings": self.ai_settings,
                "today_trade_count": today_trade_count,
                "today_realized_pnl": round(today_realized_pnl, 2),
                "kalshi_connected": kalshi_trader.is_authenticated(),
                "balance_dollars": balance_info.get("balance_dollars", 0.0),
                "balance_cents": balance_info.get("balance_cents", 0),
                "total_trades": total_trades,
                "wins": wins,
                "losses": losses,
                "win_rate_pct": win_rate,
                "total_pnl_dollars": round(total_pnl, 2),
                "open_trades_count": len(annotated_open_trades),
                "open_trades": annotated_open_trades,
                "open_pnl_dollars": round(open_pnl_dollars, 4),   # live unrealized P&L
                "recent_trades": [
                    next((a for a in annotated_open_trades if a.get("id") == t.get("id")), t)
                    for t in mode_trades[-15:][::-1]
                ],  # latest 15 trades of current mode first
                "active_market": active_market,
                "prediction_accuracy": prediction_accuracy,
            }

        def reset_prediction_accuracy(self):
            with _history_lock:
                trades = self.get_trades_history()
                modified = False
                for trade in trades:
                    if trade.get("accuracy_eligible", True):
                        trade["accuracy_eligible"] = False
                        modified = True
                
                if modified:
                    self._save_trades_history(trades)
            return {"status": "ok"}

        def get_prediction_accuracy(self, trades: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
            """Return accuracy for settled, automated predictions only.
    
            Historical manual/scalp records deliberately remain in the ledger but are
            not valid inputs for this metric because they do not share an analyzer
            prediction ID and official Kalshi outcome.
            """
            if trades is None:
                trades = self.get_trades_history()
    
            settled = [
                trade for trade in trades
                if trade.get("prediction_kind") == "AUTO"
                and trade.get("prediction_id")
                and trade.get("accuracy_eligible", True)
                and trade.get("status") == "SETTLED"
                and isinstance(trade.get("prediction_correct"), bool)
            ][-100:]
    
            correct = sum(1 for trade in settled if trade.get("prediction_correct"))
            total = len(settled)
            daily_history: Dict[str, Dict[str, int]] = {}
            outcomes: List[Dict[str, Any]] = []
            for trade in settled:
                day = str(trade.get("settled_at") or trade.get("timestamp") or "")[:10]
                if day:
                    stats = daily_history.setdefault(day, {"correct": 0, "total": 0})
                    stats["total"] += 1
                    if trade.get("prediction_correct"):
                        stats["correct"] += 1
    
                actual_result = str(trade.get("official_result", "")).upper()
                outcome = {
                    "correct": bool(trade.get("prediction_correct")),
                    "predicted": trade.get("prediction_direction", trade.get("direction", "")),
                    "actual": "ABOVE" if actual_result == "YES" else "BELOW" if actual_result == "NO" else actual_result,
                    "time": trade.get("settled_at") or trade.get("timestamp"),
                    "settled_at": trade.get("settled_at") or trade.get("timestamp"),
                    "pnl": trade.get("pnl", 0.0),
                    "conviction_grade": trade.get("conviction_grade", ""),
                    "confidence": trade.get("probability_percent"),
                }
                try:
                    target = float(trade.get("strike"))
                    settle = float(trade.get("settle_price"))
                    if target > 0 and settle > 0:
                        outcome.update({"target": target, "settle": settle})
                except (TypeError, ValueError):
                    pass
                outcomes.append(outcome)
    
            return {
                "source": "server_auto_predictions",
                "total_evaluated": total,
                "correct_picks": correct,
                "accuracy_percent": round((correct / total) * 100, 1) if total else None,
                "ratio_text": f"{correct} of {total} Correct",
                "recent_outcomes": outcomes[-5:],
                "daily_history": daily_history,
            }

        def check_and_execute_rollover(self) -> Optional[Dict[str, Any]]:
            self._load_config()
            """
            Core autonomous trigger:
            Evaluates at rollover (first 60 seconds of a new 15-minute contract interval).
            """
            # FIX #2: Acquire the lock FIRST so that the last_check_time read/write is
            # also serialized.  Previously both gates were outside the lock, creating a
            # narrow window where two threads could both pass the 4-second check and both
            # enter the expensive ML + network path.
            if not self._rollover_lock.acquire(blocking=False):
                logger.debug("[AutoExecutor] Rollover evaluation already in progress by another worker. Skipping concurrent execution.")
                return None
    
            lock_held = True
            try:
                now = time.time()
                if (now - self.last_check_time) < 0.95:
                    return None
                self.last_check_time = now
    
                if not is_market_open(self.asset):
                    logger.debug(f"[AutoExecutor] {self.asset} market is closed; skipping rollover evaluation.")
                    return None
    
                countdown_info = get_candle_countdown(timeframe="15m")
                sec_left = countdown_info.get("seconds_left", 900)
                sec_elapsed = 900 - sec_left
    
                trading_style = str(self.ai_settings.get("tradingStyle", "SNIPER")).upper()
                is_rollover_window = sec_elapsed <= 60 or sec_left >= 840
                is_prediction_window = 30 <= sec_elapsed <= 55 or 845 <= sec_left <= 870
                
                if trading_style in ["MOMENTUM_SURFER", "AMBUSH", "AUTO"]:
                    window_valid = sec_left >= 180  # No entries within 3 minutes of contract expiry
                elif trading_style == "PREDICTION":
                    # Wait up to 1m 30s (90s) for opening noise/chop to settle, then enter before the 3m expiry cutoff
                    window_valid = (sec_elapsed >= 90 and sec_left >= 180)
                    if not window_valid and sec_elapsed < 90:
                        logger.debug(f"[AutoExecutor] [PREDICTION] Waiting up to 1 minute 30 seconds for opening candle noise to settle ({sec_elapsed:.0f}s elapsed < 90s).")
                else:
                    window_valid = is_prediction_window if self.prediction_mode else is_rollover_window
    
                if not window_valid:
                    return None
    
                # Fetch active Kalshi KXBTC15M market (require at least 180s before close)
                active_m = kalshi_trader.get_active_15m_market(series_ticker=f"KX{self.asset}15M", allow_synthetic=False, min_seconds_left=180)  # no trades on the offline placeholder market
                if not active_m:
                    logger.debug("[AutoExecutor] No active market")
                    return None
    
                # Use market ticker for live orders if available; fallback to event_ticker
                current_interval_id = active_m.get("ticker") or active_m.get("event_ticker", "")
                if not current_interval_id or current_interval_id == self.last_traded_interval:
                    logger.debug(f"[AutoExecutor] Skipping because interval is last_traded_interval: {current_interval_id}")
                    return None
    
                # Check if already traded in history
                trades = self.get_trades_history()
                if any(t.get("ticker") == current_interval_id for t in trades):
                    self.last_traded_interval = current_interval_id
                    logger.debug(f"[AutoExecutor] Already traded interval {current_interval_id} in trades history")
                    return None
    
                # Finding 4: Re-check last_traded_interval immediately before expensive ML & network calls
                if current_interval_id == self.last_traded_interval:
                    return None
    
                # Regime penalty: after a string of recent losses (esp. false-breakout or
                # choppy-market losses), require higher confidence before trading again.
                # See loss_analyzer.calculate_regime_penalties() for the thresholds.
                regime = loss_analyzer.calculate_regime_penalties(trades)
                conviction_multiplier = float(regime.get("conviction_multiplier", 1.0))
                extra_conviction_cushion = float(regime.get("extra_min_rsi_cushion", 0.0))
                if conviction_multiplier < 1.0 or regime.get("chop_warning"):
                    logger.info(f"[AutoExecutor] Regime penalty active: {regime}")
    
                # A prediction without the contract's official target must never create
                # an order; a zero target previously made NO trades settle incorrectly.
                try:
                    strike = float(active_m.get("strike_price") or 0.0)
                except (TypeError, ValueError):
                    strike = 0.0
                if strike <= 0:
                    logger.error("[AutoExecutor] Active Kalshi market has no valid floor strike; skipping %s", current_interval_id)
                    return None
    
                # Fetch technical indicator data based on Trading Style
                tf = "15m"
                df = fetch_candles(self.asset, timeframe=tf, limit=1000)
                df_ind = add_all_indicators(df)
                
                effective_style = trading_style
                auto_regime_info = None
                if effective_style == "AUTO":
                    auto_regime_info = classify_auto_regime(df_ind, sec_left=sec_left)
                    effective_style = auto_regime_info["style"]
                    logger.info(
                        f"[AutoExecutor] Auto 2.0 Regime: {auto_regime_info['regime']} -> Routed to {effective_style} "
                        f"({auto_regime_info['reason']})"
                    )
    
                # For MOMENTUM_SURFER, use high-resolution 1m candles for precise entry timing
                if effective_style == "MOMENTUM_SURFER":
                    df_eval = fetch_candles(self.asset, timeframe="1m", limit=350)
                    df_ind_eval = add_all_indicators(df_eval)
                else:
                    df_ind_eval = df_ind
    
                # Inject historical market intervals directly into the ML Engine to train it instantly
                try:
                    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
                    ml_style = "SNIPER" if effective_style in ["AUTO", "CAPITAL_GUARD"] else effective_style
                    ml_engine = get_ml_engine(data_dir, trading_style=ml_style, asset=self.asset)
                    model_age = time.time() - getattr(ml_engine, "last_trained_mtime", 0.0)
                    if not getattr(ml_engine, "_is_training", False) and (not ml_engine.is_trained or model_age > 7 * 86400):
                        ml_engine._is_training = True
                        def _bg_train():
                            try:
                                import concurrent.futures
                                # Offload to ThreadPoolExecutor so Pandas/XGBoost don't block the GIL
                                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                                    pool.submit(_run_historical_training, data_dir, ml_style, self.asset, effective_style).result()
                            except Exception as e:
                                logger.error(f"[AutoExecutor] Background train failed: {e}")
                            finally:
                                ml_engine._is_training = False
                                ml_engine.last_trained_mtime = time.time()
                                
                        threading.Thread(target=_bg_train, daemon=True).start()
                except Exception as e:
                    logger.error(f"[AutoExecutor] Failed to self-train ML Engine: {e}")
    
                # Detect advanced chart patterns (triangles, flags, head & shoulders)
                patterns = []
                if effective_style not in ["MOMENTUM_SURFER", "CAPITAL_GUARD"]:
                    try:
                        patterns = detect_candlestick_patterns(df_ind_eval)
                    except Exception as _pat_err:
                        logger.debug(f"[AutoExecutor] Pattern detector error: {_pat_err}")
    
                if effective_style == "CAPITAL_GUARD":
                    forecast = {
                        "recommendation": "PASS / CHOP DEADZONE (CAPITAL GUARD)",
                        "direction": "PASS",
                        "action_type": "PASS",
                        "probability_percent": 50.0,
                        "predicted_probability": 0.5,
                        "ml_prob": 0.5,
                        "pre_gate_direction": "PASS",
                        "pre_gate_prob": 50.0,
                        "pre_gate_grade": "GRADE C / PASS",
                        "conviction_grade": "PASS / CHOP DEADZONE (CAPITAL GUARD)",
                        "conviction_badge": "🛡️ CAPITAL GUARD (PASS)",
                        "target_settlement_zone": "--",
                        "primary_edge": "Low-volatility compression deadzone (ADX < 18, Vol < 0.85). Preserving capital for high-edge expansion.",
                        "catalysts": ["Capital Guard active: zero edge detected"],
                        "raw_features": [],
                        "auto_regime": auto_regime_info,
                    }
                elif effective_style == "CHOP":
                    try:
                        forecast = evaluate_chop_contract(df_ind_eval, target_price=strike, kalshi_m=active_m)
                    except Exception as chop_err:
                        logger.error(
                            f"[AutoExecutor] chop_engine unavailable ({chop_err}); "
                            f"falling back to standard SNIPER evaluation for this cycle."
                        )
                        forecast = evaluate_next_15m_contract(
                            df_ind_eval, target_price=strike, patterns=patterns, kalshi_m=active_m, trading_style="SNIPER"
                        )
                else:
                    forecast = evaluate_next_15m_contract(
                        df_ind_eval, target_price=strike, patterns=patterns, kalshi_m=active_m, trading_style=effective_style
                    )
                    if auto_regime_info:
                        forecast["auto_regime"] = auto_regime_info
    
                # Hook: RL Shadow Sandbox execution
                try:
                    execute_shadow_trade(forecast, kalshi_market=active_m)
                except Exception as e:
                    logger.error(f"[ShadowExecutor Hook] Error: {e}")
    
                raw_score = float(forecast.get("probability_percent", 50.0))
                edge_label = str(forecast.get("primary_edge", ""))
                rec = forecast.get("recommendation", "")
                grade = forecast.get("conviction_grade", "")
                badge = str(forecast.get("conviction_badge", ""))
                direction = normalize_prediction_direction(forecast.get("direction") or rec)
    
                pre_gate_dir = forecast.get("pre_gate_direction")
                pre_gate_grade = str(forecast.get("pre_gate_grade", ""))
                pre_gate_prob = float(forecast.get("pre_gate_prob", raw_score))
                raw_ml_prob = float(forecast.get("raw_ml_prob", forecast.get("ml_prob", 0.5)))
                ml_prob = float(forecast.get("ml_prob", 0.5))
    
                one_shot_ai = bool(self.ai_settings.get("oneShotAiStartTrade", False))
                ignore_pass = bool(self.ai_settings.get("ignorePass", False))
                ignore_pass_technical_only = bool(self.ai_settings.get("ignorePassTechnicalOnly", False))
                reverse_cvd = bool(self.ai_settings.get("reverseCvd", False))
                is_reverse = False
                is_forced_pass = False
    
                if ("PIN RISK" in badge or "PIN RISK" in rec) and not one_shot_ai:
                    logger.info("[AutoExecutor] Strike Pin Risk active (price within $15 of strike target in low volatility). Sitting out to protect win rate.")
                    return None
    
                if (one_shot_ai or ignore_pass):
                    # 100% AI Prediction mode (until toggled off if ignore_pass, or 1-shot if one_shot_ai)
                    # Use raw unmolested ML probability directly from the model
                    ai_model_prob = raw_ml_prob
                    if ai_model_prob != 0.50:
                        direction = "ABOVE" if ai_model_prob > 0.50 else "BELOW"
                        raw_score = max(51.0, ai_model_prob * 100.0) if ai_model_prob > 0.50 else max(51.0, (1.0 - ai_model_prob) * 100.0)
                    else:
                        if pre_gate_dir in ["ABOVE", "BELOW"]:
                            direction = pre_gate_dir
                        else:
                            trend_1h = forecast.get("trend_1h", "NEUTRAL")
                            if trend_1h == "BULLISH":
                                direction = "ABOVE"
                            elif trend_1h == "BEARISH":
                                direction = "BELOW"
                            else:
                                return None
                        raw_score = pre_gate_prob if pre_gate_prob else 51.0
    
                    if pre_gate_prob and pre_gate_dir == direction and pre_gate_prob > raw_score:
                        raw_score = pre_gate_prob
    
                    grade = "GRADE A+ (100% AI)"
                    badge = f"🎯 100% AI ({raw_score:.0f}%)"
                    rec = f"100% AI Prediction{' (Force Trade)' if ignore_pass else ' at Start'}: {'YES' if direction == 'ABOVE' else 'NO'}"
                    is_forced_pass = True
                    logger.info(
                        f"[AutoExecutor] [{'100% AI MODE (UNTIL TOGGLED OFF)' if ignore_pass else '1-SHOT AI MODE'}] Trading 100% on AI Prediction: "
                        f"{direction} ({raw_score:.1f}% Conf, Raw ML: {ai_model_prob*100:.1f}%). Technical and PASS filters bypassed."
                    )
                    if ignore_pass:
                        logger.warning(
                            "[AutoExecutor] 'Force Trade on PASS' is ENABLED — bypassing 1H-trend, "
                            "CVD, orderbook, and chop safety gates on this trade. This trades off "
                            "accuracy for frequency; verify this is intentional."
                        )
                elif ignore_pass_technical_only and direction == "PASS":
                    # Only force trade if there was a real technical chart setup detected (not just ML fallback)
                    if "ML MODEL" not in pre_gate_grade and pre_gate_dir in ["ABOVE", "BELOW"]:
                        direction = pre_gate_dir
                        raw_score = pre_gate_prob
                        grade = "GRADE A+ (TECH FORCE)"
                        badge = f"🎯 TECH FORCE ({raw_score:.0f}%)"
                        rec = f"Technical Force Trade: {'YES' if direction == 'ABOVE' else 'NO'}"
                        is_forced_pass = True
                        logger.info(f"[AutoExecutor] [TECHNICAL FORCE TRADE] Overriding PASS using Technical Setup: {direction} ({raw_score:.1f}% Conf). ML/Macro blockers bypassed.")
                    else:
                        logger.info("[AutoExecutor] [TECHNICAL FORCE TRADE] Active, but no technical chart setup was present. Remaining PASS.")
                        return None
                # Handle PASS direction filtering or CVD Divergence
                elif direction == "PASS":
                    # Determine best underlying direction from pre-gate analysis or ML model
                    if pre_gate_dir in ["ABOVE", "BELOW"]:
                        best_underlying_dir = pre_gate_dir
                        best_underlying_prob = pre_gate_prob
                    elif ml_prob != 0.5:
                        best_underlying_dir = "ABOVE" if ml_prob >= 0.5 else "BELOW"
                        best_underlying_prob = ml_prob * 100.0 if ml_prob >= 0.5 else (1.0 - ml_prob) * 100.0
                    else:
                        best_underlying_dir = "ABOVE" if raw_score >= 50.0 else "BELOW"
                        best_underlying_prob = raw_score
    
                    if reverse_cvd and "CVD DIVERGENCE" in badge:
                        original_dir = best_underlying_dir
                        direction = "BELOW" if original_dir == "ABOVE" else "ABOVE"
                        is_reverse = True
                        raw_score = best_underlying_prob
                        logger.info(f"[AutoExecutor] 'Reverse on CVD Divergence' enabled. Reversing {original_dir} trade to {direction} (Score: {raw_score:.1f}%).")
                    else:
                        logger.debug("[AutoExecutor] Skipping because direction is PASS")
                        return None
                elif reverse_cvd and "CVD DIVERGENCE" in badge and raw_score > 0:
                    original_dir = direction
                    direction = "BELOW" if original_dir == "ABOVE" else "ABOVE"
                    is_reverse = True
                    logger.info(f"[AutoExecutor] 'Reverse on CVD Divergence' enabled. Reversing active {original_dir} trade to {direction}.")
    
                # Strict Filter 2: Conviction & Settings Thresholds
                meets_conviction = False
            
                # ML settings overrides
                min_conf = float(self.ai_settings.get("minConf", 0.0))
                edge_multiplier = float(self.ai_settings.get("edgeWeightFactor", 1.0)) if self.ai_settings.get("edgeWeightOn") else 1.0
            
                actual_conf = raw_score
                if "High Confluence" in edge_label:
                    actual_conf = min(99.0, raw_score * edge_multiplier)
    
                # Dampen confidence after a rough recent stretch (see Step 2b above).
                # A multiplier < 1.0 makes both the min_conf check and the ML-fallback
                # gate below harder to satisfy, which is the intended effect.
                actual_conf = actual_conf * conviction_multiplier
    
                # Base threshold check against minConf
                applied_threshold = min_conf
                if one_shot_ai:
                    meets_conviction = True
                elif is_forced_pass or is_reverse:
                    # User explicitly requested Force Trade on PASS or Reverse on CVD Divergence
                    meets_conviction = True
                    logger.info(f"[AutoExecutor] Conviction check bypassed for forced/reversed trade ({direction} @ {actual_conf:.1f}%).")
                elif isinstance(self.ai_settings.get("minConfByGrade"), dict):
                    floors = self.ai_settings["minConfByGrade"]
                    if "A+" in grade:
                        applied_threshold = float(floors.get("A_PLUS", 70))
                    elif "GRADE A " in grade or "GRADE A SETUP" in grade:
                        applied_threshold = float(floors.get("A", 65))
                    elif "B SETUP" in grade:
                        applied_threshold = float(floors.get("B", 60))
                    else:
                        applied_threshold = float(floors.get("ML_FALLBACK", 65))
                    if actual_conf >= applied_threshold:
                        meets_conviction = True
                elif min_conf > 0:
                    if actual_conf >= min_conf:
                        meets_conviction = True
                else:
                    # Fallback to grade logic
                    if self.prediction_mode:
                        meets_conviction = True
                    else:
                        # A "GRADE C / ML MODEL" label is the fallback used when no real
                        # chart/technical setup fired; only let it satisfy a higher
                        # conviction bar when its own confidence is meaningfully away
                        # from a coin-flip (50%), never on the label text alone.
                        ml_fallback_hi = 65.0 + extra_conviction_cushion
                        ml_fallback_lo = 35.0 - extra_conviction_cushion
                        is_confident_ml_fallback = ("GRADE C" in grade and "ML MODEL" in grade) and (actual_conf >= ml_fallback_hi or actual_conf <= ml_fallback_lo)
    
                        if effective_style == "MOMENTUM_SURFER":
                            # Dynamic Confidence Minimums for Machine Gun Mode
                            min_conf = 60.0 if sec_elapsed <= 60 else 75.0
                            actual_win_conf = max(actual_conf, 100.0 - actual_conf)
                            meets_conviction = (actual_win_conf >= min_conf)
                        elif effective_style == "PREDICTION":
                            # Prediction style waits 1m 30s for opening noise to settle; requires conviction >= 55%
                            actual_win_conf = max(actual_conf, 100.0 - actual_conf)
                            min_pred_conf = max(55.0, min_conf)
                            meets_conviction = (actual_win_conf >= min_pred_conf)
                            if not meets_conviction:
                                logger.info(f"[AutoExecutor] [PREDICTION] Skipped: confidence {actual_win_conf:.1f}% below minimum {min_pred_conf:.1f}%")
                        else:
                            if effective_style == "CHOP":
                                meets_conviction = ("CHOP" in grade) and (actual_conf >= min_conf)
                            elif self.min_conviction == "GRADE A+ SETUP" and "A+" in grade:
                                meets_conviction = True
                            elif self.min_conviction == "GRADE A SETUP" and ("A+" in grade or "GRADE A " in grade or is_confident_ml_fallback):
                                meets_conviction = True
                            elif self.min_conviction == "GRADE B+ SETUP" and ("A+" in grade or "GRADE A " in grade or "B+ SETUP" in grade or is_confident_ml_fallback):
                                meets_conviction = True
                            elif self.min_conviction == "GRADE B SETUP" and ("A+" in grade or "GRADE A " in grade or "B+ SETUP" in grade or "B SETUP" in grade or is_confident_ml_fallback):
                                meets_conviction = True
    
                if not meets_conviction:
                    logger.debug(f"[AutoExecutor] Skipping because conviction not met: {actual_conf} < {applied_threshold} (Grade: {grade})")
                    return None
    
                # If bot is disabled, do not execute
                if not self.enabled:
                    logger.debug("[AutoExecutor] Skipping because bot is disabled")
                    return None
    
                # Strict Filter 3: Enforce Max Daily Trades & Max Daily Risk (Finding 2)
                risk_blocked_reason = self.check_risk_budget(trades)
                if risk_blocked_reason:
                    logger.info(f"[AutoExecutor] {risk_blocked_reason}. Skipping auto execution.")
                    return None
    
                # Physical Chart Direction and Spot Alignment Guard
                # Ensure trades align with real candle direction, moving average momentum, and spot delta relative to strike
                is_oversold_bounce = ("Absorption Hammer" in str(forecast.get("catalysts", [])) or "Oversold Spring" in str(forecast.get("catalysts", [])) or "Bullish Liquidity Sweep" in str(forecast.get("catalysts", [])))
                is_overbought_fade = ("Rejection Pin" in str(forecast.get("catalysts", [])) or "Overbought Exhaustion" in str(forecast.get("catalysts", [])) or "Bearish Liquidity Sweep" in str(forecast.get("catalysts", [])))
    
                c_eval = df_ind_eval.iloc[-1]
                c_open = float(c_eval["open"])
                c_close = float(c_eval["close"])
                c_ema9 = float(c_eval.get("ema_9", c_close))
                c_ema21 = float(c_eval.get("ema_21", c_close))
                delta_strike = c_close - strike
    
                chart_conflict = False
                conflict_reason = ""
    
                if direction == "ABOVE":
                    # User wants ABOVE (YES), anticipating settlement >= strike
                    # Fighting chart if: price is deeply below strike AND both candle and EMA momentum are bearish
                    if delta_strike < -25.0 and (c_close < c_open) and (c_ema9 < c_ema21) and not is_oversold_bounce:
                        chart_conflict = True
                        conflict_reason = f"Spot ${c_close:,.2f} is ${abs(delta_strike):.2f} below strike ${strike:,.2f} with red candle and EMA9 < EMA21"
                elif direction == "BELOW":
                    # User wants BELOW (NO), anticipating settlement < strike
                    # Fighting chart if: price is deeply above strike AND both candle and EMA momentum are bullish
                    if delta_strike > 25.0 and (c_close > c_open) and (c_ema9 > c_ema21) and not is_overbought_fade:
                        chart_conflict = True
                        conflict_reason = f"Spot ${c_close:,.2f} is ${delta_strike:.2f} above strike ${strike:,.2f} with green candle and EMA9 > EMA21"
    
                if chart_conflict:
                    logger.warning(
                        f"[AutoExecutor] 🛑 Chart Trend Conflict Blocked: Direction {direction} contradicts physical chart trend ({conflict_reason}). Skipping trade."
                    )
                    return None
    
                # Map signal to Kalshi contract side
                # "ABOVE" -> buy YES (anticipating price >= strike)
                # "BELOW" -> buy NO (anticipating price < strike)
                side = "yes" if direction == "ABOVE" else "no"
                market_price = active_m.get("yes_ask" if side == "yes" else "no_ask") or 0.50
    
                # Determine affordable contract count for live or paper
            
                # ML Settings Overrides: Use maxCap or trade_size_dollars to size position
                max_cap = float(self.ai_settings.get("maxCap", 0.0))
                if max_cap <= 0:
                    max_cap = float(self.ai_settings.get("paper_trade_size_dollars" if self.mode == "PAPER" else "trade_size_dollars", 0.0) or self.ai_settings.get("trade_size_dollars", 0.0) or 0.0)
                unit_price_est = min(0.99, max(0.01, float(market_price) + 0.04))
            
                # AUDIT FIX #3: Hard ceiling on contracts to prevent black-swan order sizes
                ABSOLUTE_MAX_CONTRACTS = 999999
    
                use_kelly = bool(self.ai_settings.get("useKellyCriterion", False)) or bool(self.ai_settings.get("use_kelly_criterion", False))
                if use_kelly:
                    p_win = float(actual_conf) / 100.0 if actual_conf else 0.50
                    b_price = float(market_price)
                    if p_win <= b_price:
                        logger.info(f"[AutoExecutor] Kelly Criterion (-EV Setup): Skipping {side.upper()} @ ${b_price:.2f} (win prob {p_win*100:.1f}% <= price ${b_price:.2f})")
                        return None
                    edge = p_win - b_price
                    kelly_frac = min(1.0, max(0.25, edge / 0.15))
                    base_dollars = (max_cap if max_cap > 0 else (self.max_contracts * unit_price_est)) * kelly_frac
                    contracts_to_buy = max(1, int(base_dollars / unit_price_est))
                elif max_cap > 0:
                    contracts_to_buy = int(max_cap / unit_price_est)
                    if contracts_to_buy < 1:
                        contracts_to_buy = 1
                else:
                    contracts_to_buy = self.max_contracts
            
                contracts_to_buy = min(contracts_to_buy, ABSOLUTE_MAX_CONTRACTS)
    
                # 2. Dry Run
                dry_run = (self.mode == "PAPER")
                if self.ai_settings.get("dryRun", False):
                    dry_run = True
    
                # 3. Execution Delay — FIX #4: release the lock while sleeping so the
                # background loop isn't stalled for the full delay duration.
                exec_delay = int(self.ai_settings.get("execDelay", 0))
                if exec_delay > 0:
                    logger.info(f"[AutoExecutor] Delaying execution by {exec_delay}s (lock released during wait)...")
                    self._rollover_lock.release()
                    lock_held = False
                    try:
                        time.sleep(exec_delay)
                    finally:
                        lock_held = self._rollover_lock.acquire(blocking=True, timeout=10)
                        if not lock_held:
                            logger.error("[AutoExecutor] Could not re-acquire rollover lock after exec_delay sleep; aborting trade.")
                            return None
                
    
                paper_avail_bal = None
                if self.mode == "LIVE":

                    bal_res = kalshi_trader.get_balance()
                    if bal_res.get("success", False):
                        avail_bal = float(bal_res.get("balance_dollars", 0.0))
                        unit_price = min(0.99, max(0.01, float(market_price) + 0.04))
                        if unit_price > 0 and avail_bal < (unit_price * contracts_to_buy):
                            affordable = int(avail_bal / unit_price)
                            contracts_to_buy = affordable
                else:
                    # PAPER: clamp to what the paper balance can actually afford, same as LIVE
                    # does against the real account balance above - a paper account shouldn't be
                    # able to size a trade its own balance couldn't cover.
                    paper_avail_bal = load_balance(guest_id=getattr(self, '_guest_id', None))
                    unit_price = min(0.99, max(0.01, float(market_price) + 0.04))
                    if unit_price > 0 and paper_avail_bal < (unit_price * contracts_to_buy):
                        contracts_to_buy = int(paper_avail_bal / unit_price)

                if contracts_to_buy < 1:
                    logger.warning("Insufficient balance to execute trade. Skipping.")
                    return None

                slippage_buffer = float(self.ai_settings.get("slippageBufferDollars", self.ai_settings.get("slippageBufferCents", 0.04)))

                # M-DUP: one automated LIVE entry per account per market, enforced in users.db
                # so it holds across loops, processes and restarts (see order_intents.py).
                intent_key = None
                if not dry_run:
                    intent_key = order_intents.account_key_for_executor(getattr(self, '_guest_id', None))
                    if not order_intents.claim(intent_key, current_interval_id, side):
                        logger.warning(
                            f"[AutoExecutor] LIVE entry already attempted for '{current_interval_id}' "
                            f"(order_intents). Not sending another order this interval."
                        )
                        self.last_traded_interval = current_interval_id
                        return None

                # Execute Order (Paper or Live)
                order_res = kalshi_trader.place_order(
                    ticker=current_interval_id,
                    side=side,
                    count=contracts_to_buy,
                    limit_price_dollars=market_price,
                    dry_run=dry_run,
                    slippage_buffer_dollars=slippage_buffer,
                    available_balance=paper_avail_bal
                )
                if intent_key:
                    order_intents.settle_outcome(intent_key, current_interval_id, order_res)
    
                if order_res.get("success", False):
                    # SaaS Broadcast
                    # SaaS broadcasting is now handled concurrently by evaluate_and_execute_saas_users()
    
                    # Finding 9: Verify order response ticker matches current_interval_id
                    res_ticker = order_res.get("ticker") or (order_res.get("order") or {}).get("ticker")
                    if res_ticker and str(res_ticker).strip() != str(current_interval_id).strip():
                        logger.error(
                            f"[AutoExecutor] Ticker mismatch! Expected interval '{current_interval_id}', "
                            f"order executed on '{res_ticker}'. Aborting trade record creation to prevent corrupted stats/ML training."
                        )
                        return None
    
                    # H1 & H2: Record actual fill metrics and fix paper balance cost key
                    fill_price = float(order_res.get("filled_price", market_price))
                    fill_count = float(order_res.get("count", contracts_to_buy))
                    fill_cost = float(order_res.get("total_cost", round(fill_price * fill_count, 4)))
    
                    if self.mode == "PAPER":
                        try:
                            update_balance(-(fill_cost + kalshi_order_fee(fill_price, fill_count)), guest_id=getattr(self, '_guest_id', None))
                        except Exception as e:
                            logger.error(f"Paper deduction error: {e}")
                    elif self.mode == "LIVE":
                        kalshi_trader.get_balance(force_refresh=True)
    
                    self.last_traded_interval = current_interval_id
                    # The prediction record is the single source carried from analyzer
                    # to order to accuracy.  It deliberately uses a different ID from
                    # Kalshi's order ID so retries cannot rewrite its identity.
                    prediction_id = str(uuid.uuid4())
                    prediction_generated_at = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET")
                    close_time_str = active_m.get("close_time") or ""
                    close_epoch = now + sec_left
                    if close_time_str:
                        try:
                            close_epoch = datetime.fromisoformat(close_time_str.replace("Z", "+00:00")).timestamp()
                        except (TypeError, ValueError):
                            pass
    
                    trade_record = {
                        "id": order_res.get("order_id", str(uuid.uuid4())[:8]),
                        "client_order_id": order_res.get("client_order_id", ""),
                        "timestamp": prediction_generated_at,
                        "prediction_id": prediction_id,
                        "prediction_kind": "AUTO",
                        "trade_source": f"AUTO ({effective_style})" if not is_reverse else f"AUTO ({effective_style}) - REVERSE",
                        "is_auto": True,
                        "is_reverse": is_reverse,
                        "is_forced_pass": is_forced_pass,
                        "is_scalp": False,
                        "trading_style": effective_style,
                        "prediction_direction": direction,
                        "prediction_generated_at": prediction_generated_at,
                        "accuracy_eligible": True,
                        "interval_close_time": close_time_str,
                        "close_epoch": close_epoch,
                        "ticker": current_interval_id,
                        "title": active_m.get("title", ""),
                        "market_snapshot": {
                            "price": float(df_ind.iloc[-1]["close"]) if len(df_ind) > 0 else float(strike),
                            "target": strike,
                            "confidence": int(raw_score) if (one_shot_ai or is_forced_pass or is_reverse) else forecast.get("probability_percent"),
                            "conviction_grade": forecast.get("conviction_grade"),
                            "primary_edge": forecast.get("primary_edge"),
                            "raw_features": forecast.get("raw_features", {})
                        },
                        "strike": strike,
                        "direction": direction,
                        "recommendation": rec,
                        "conviction_grade": grade,
                        "conviction_badge": badge if (one_shot_ai or ignore_pass) else forecast.get("conviction_badge", ""),
                        "probability_percent": int(raw_score) if (one_shot_ai or is_forced_pass or is_reverse) else forecast.get("probability_percent", 50),
                        "predicted_probability": round(float(raw_score) / 100.0, 4) if (one_shot_ai or is_forced_pass or is_reverse) else forecast.get("predicted_probability", round(float(forecast.get("probability_percent", 50)) / 100.0, 4)),
                        "ml_prob": round(float(raw_ml_prob if (one_shot_ai or ignore_pass) else ml_prob), 4),
                        "side": side.upper(),
                        "requested_price": market_price,
                        "entry_price": fill_price,
                        "requested_count": contracts_to_buy,
                        "count": fill_count,
                        "cost": fill_cost,
                        "slippage_cents": round(abs(fill_price - market_price), 4),
                        "slippage_buffer_used": slippage_buffer,
                        "mode": str(order_res.get("mode", self.mode)).upper(),
                        "status": "OPEN",
                        "result": "PENDING",
                        "pnl": 0.0,
                        "catalysts": [f"100% AI Prediction{' (Force Trade)' if ignore_pass else ' at Start'}: AI model predicted {raw_score:.1f}% {'UP' if direction == 'ABOVE' else 'DOWN'}"] + list(forecast.get("catalysts", [])) if (one_shot_ai or ignore_pass) else forecast.get("catalysts", [])
                    }
    
                    trades.append(trade_record)
                    self._save_trades_history(trades)
    
                    # Auto-reset oneShotAiStartTrade back to normal (OFF) after placing trade
                    # Note: ignorePass (Force Trade on PASS) remains active continuously on every trade until explicitly toggled off by user
                    if one_shot_ai and not ignore_pass:
                        self.ai_settings["oneShotAiStartTrade"] = False
                        self._save_config()
                        logger.info("[AutoExecutor] [1-SHOT AI MODE] Trade executed! Auto-resetting 'oneShotAiStartTrade' back to normal (OFF).")
    
                    # Connect with scalp_engine for early profit exits if scalping is enabled
                    try:
                        if getattr(scalp_engine, "enabled", False):
                            scalp_engine.register_position(trade_record)
                    except Exception as se_err:
                        logger.warning(f"[AutoExecutor] Could not register trade with ScalpEngine: {se_err}")
    
                else:
                    if order_res.get("ambiguous"):
                        # It may have filled: treat this interval as traded so no second order goes out.
                        self.last_traded_interval = current_interval_id
                        logger.error(
                            f"[AutoExecutor] CRITICAL: Rollover order outcome ambiguous after timeout! "
                            f"Interval: '{current_interval_id}', Ticker: '{order_res.get('ticker', current_interval_id)}', "
                            f"Client Order ID: '{order_res.get('client_order_id')}'. "
                            f"Error: {order_res.get('error')}. MANUAL VERIFICATION REQUIRED ON KALSHI."
                        )
                    else:
                        logger.error(f"[AutoExecutor] Order failed: {order_res.get('error')}")
    
                return None
            finally:
                if lock_held:
                    self._rollover_lock.release()

        def execute_manual_trade(self, direction: str, is_reversal: bool = False) -> Dict[str, Any]:
            self._load_config()
            """
            Enables user to click 1-click execution for the current interval directly from the UI.
            """
            dir_clean = str(direction or "").upper().strip()
            one_shot_active = bool(self.ai_settings.get("oneShotAiStartTrade", False)) or dir_clean in ["AI_START", "AI", "AUTO"]
    
            # Finding 2: Enforce shared daily risk budget on manual trades
            if not is_reversal:
                risk_blocked_reason = self.check_risk_budget()
                if risk_blocked_reason:
                    logger.info(f"[AutoExecutor] Manual trade blocked: {risk_blocked_reason}")
                    return {"success": False, "error": risk_blocked_reason}
    
            active_m = kalshi_trader.get_active_15m_market(series_ticker=f"KX{self.asset}15M", allow_synthetic=False, min_seconds_left=30)
            if not active_m:
                return {"success": False, "error": f"No active KX{self.asset}15M market found (>30s before expiration required)."}
    
            if dir_clean in ["AI_START", "AI", "AUTO"]:
                try:
                    df = fetch_candles(self.asset, timeframe="15m", limit=350)
                    df_ind = add_all_indicators(df)
                    forecast = evaluate_next_15m_contract(df_ind, kalshi_m=active_m)
                    # Use the blended forecast direction (same signal shown in the UI prediction panel)
                    # NOT raw ml_prob alone — that can disagree with the displayed prediction
                    forecast_dir = str(forecast.get("direction", "")).upper().strip()
                    if forecast_dir in ["ABOVE", "UP", "YES"]:
                        dir_clean = "ABOVE"
                    elif forecast_dir in ["BELOW", "DOWN", "NO"]:
                        dir_clean = "BELOW"
                    else:
                        # Fallback: use ml_prob only if direction is ambiguous/PASS
                        ml_prob = float(forecast.get("ml_prob", 0.5))
                        if ml_prob > 0.50:
                            dir_clean = "ABOVE"
                        elif ml_prob < 0.50:
                            dir_clean = "BELOW"
                        else:
                            trend = str(forecast.get("raw_features", {}).get("trend_1h", "UP")).upper()
                            ema_9 = float(forecast.get("raw_features", {}).get("ema_9", 0))
                            ema_21 = float(forecast.get("raw_features", {}).get("ema_21", 0))
                            if trend in ["UP", "BULLISH"] or (ema_9 > ema_21 and ema_21 > 0):
                                dir_clean = "ABOVE"
                            else:
                                dir_clean = "BELOW"
                        logger.warning(f"[AutoExecutor] AI_START: forecast direction was '{forecast_dir}', falling back to ml_prob={ml_prob:.3f} -> {dir_clean}")
                except Exception as _ai_err:
                    logger.error(f"[AutoExecutor] Error resolving AI start direction: {_ai_err}")
                    dir_clean = "ABOVE"
    
            if dir_clean not in ["ABOVE", "BELOW"]:
                return {"success": False, "error": f"Invalid trade direction: '{direction}'. Must be 'ABOVE' or 'BELOW'."}
    
            side = "yes" if dir_clean == "ABOVE" else "no"
            market_price = active_m.get("yes_ask" if side == "yes" else "no_ask") or 0.50
    
            # Determine affordable contract count for live or paper
            
            # ML Settings Overrides: Use maxCap or trade_size_dollars to size position
            max_cap = float(self.ai_settings.get("maxCap", 0.0))
            if max_cap <= 0:
                max_cap = float(self.ai_settings.get("paper_trade_size_dollars" if self.mode == "PAPER" else "trade_size_dollars", 0.0) or self.ai_settings.get("trade_size_dollars", 0.0) or 0.0)
            unit_price_est = min(0.99, max(0.01, float(market_price) + 0.04))
            
            ABSOLUTE_MAX_CONTRACTS = 999999
            use_kelly = bool(self.ai_settings.get("useKellyCriterion", False)) or bool(self.ai_settings.get("use_kelly_criterion", False))
            if use_kelly:
                p_win = float(conf) / 100.0 if ('conf' in locals() and conf) else 0.50
                b_price = float(market_price)
                if p_win <= b_price:
                    logger.info(f"[AutoExecutor] Kelly Criterion (-EV Setup): Skipping {side.upper()} @ ${b_price:.2f} (win prob {p_win*100:.1f}% <= price ${b_price:.2f})")
                    return {"success": False, "error": f"Kelly Criterion: -EV setup (prob {p_win*100:.1f}% <= price ${b_price:.2f})"}
                edge = p_win - b_price
                kelly_frac = min(1.0, max(0.25, edge / 0.15))
                base_dollars = (max_cap if max_cap > 0 else (self.max_contracts * unit_price_est)) * kelly_frac
                contracts_to_buy = max(1, int(base_dollars / unit_price_est))
            elif max_cap > 0:
                contracts_to_buy = int(max_cap / unit_price_est)
                if contracts_to_buy < 1:
                    contracts_to_buy = 1
            else:
                contracts_to_buy = self.max_contracts
    
            contracts_to_buy = min(contracts_to_buy, ABSOLUTE_MAX_CONTRACTS)
    
            # 2. Dry Run
            dry_run = (self.mode == "PAPER")
            if self.ai_settings.get("dryRun", False):
                dry_run = True
    
            paper_avail_bal = None
            if self.mode == "LIVE":

                bal_res = kalshi_trader.get_balance()
                if bal_res.get("success", False):
                    avail_bal = float(bal_res.get("balance_dollars", 0.0))
                    unit_price = min(0.99, max(0.01, float(market_price) + 0.04))
                    if unit_price > 0 and avail_bal < (unit_price * contracts_to_buy):
                        affordable = int(avail_bal / unit_price)
                        contracts_to_buy = affordable
            else:
                # PAPER: clamp to what the paper balance can actually afford, same as LIVE
                # does against the real account balance above.
                paper_avail_bal = load_balance(guest_id=getattr(self, '_guest_id', None))
                unit_price = min(0.99, max(0.01, float(market_price) + 0.04))
                if unit_price > 0 and paper_avail_bal < (unit_price * contracts_to_buy):
                    contracts_to_buy = int(paper_avail_bal / unit_price)

            if contracts_to_buy < 1:
                logger.warning("Insufficient balance to execute trade. Skipping.")
                return None

            slippage_buffer = float(self.ai_settings.get("slippageBufferDollars", self.ai_settings.get("slippageBufferCents", 0.04)))

            order_res = kalshi_trader.place_order(
                ticker=active_m.get("ticker", ""),
                side=side,
                count=contracts_to_buy,
                limit_price_dollars=market_price,
                dry_run=dry_run,
                slippage_buffer_dollars=slippage_buffer,
                available_balance=paper_avail_bal
            )
    
            if order_res.get("success", False):
                # SaaS Broadcast
                # SaaS broadcasting is now handled concurrently by evaluate_and_execute_saas_users()
                # self._broadcast_trade_to_users(active_m.get("ticker", ""), side, market_price, {})
    
                # H1 & H2: Record actual fill metrics and fix paper balance cost key
                fill_price = float(order_res.get("filled_price", market_price))
                fill_count = float(order_res.get("count", contracts_to_buy))
                fill_cost = float(order_res.get("total_cost", round(fill_price * fill_count, 4)))
    
                if self.mode == "PAPER":
                    try:
                        update_balance(-(fill_cost + kalshi_order_fee(fill_price, fill_count)), guest_id=getattr(self, '_guest_id', None))
                    except Exception as e:
                        logger.error(f"Paper deduction error: {e}")
                elif self.mode == "LIVE":
                    kalshi_trader.get_balance(force_refresh=True)
    
                trades = self.get_trades_history()
                close_time_str = active_m.get("close_time", "")
                countdown_info = get_candle_countdown(timeframe="15m")
                sec_left = countdown_info.get("seconds_left", 900)
    
                strike_val = active_m.get("strike_price")
                if not strike_val:
                    target_data = get_live_15m_target_data()
                    strike_val = target_data.get("target_price") or get_btc_ticker(self.asset).get("price", 78000.0)
    
                trade_record = {
                    "id": order_res.get("order_id", str(uuid.uuid4())[:8]),
                    "client_order_id": order_res.get("client_order_id", ""),
                    "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                    "interval_close_time": close_time_str,
                    "close_epoch": time.time() + sec_left,
                    "ticker": active_m.get("ticker", ""),
                    "title": active_m.get("title", f"Bitcoin above ${strike_val:,.2f}"),
                    "strike": strike_val,
                    "direction": direction.upper(),
                    "recommendation": f"MANUAL {direction.upper()} ({side.upper()})",
                    "conviction_grade": "MANUAL OVERRIDE",
                    "conviction_badge": "MANUAL TRADE",
                    "probability_percent": 65,
                    "trade_source": "MANUAL",
                    "trading_style": "MANUAL",
                    "is_auto": False,
                    "is_manual": True,
                    "is_scalp": False,
                    "is_reverse": False,
                    "side": side.upper(),
                    "requested_price": market_price,
                    "entry_price": fill_price,
                    "requested_count": contracts_to_buy,
                    "count": fill_count,
                    "cost": fill_cost,
                    "slippage_cents": round(abs(fill_price - market_price), 4),
                    "slippage_buffer_used": slippage_buffer,
                    "mode": str(order_res.get("mode", self.mode)).upper(),
                    "status": "OPEN",
                    "result": "PENDING",
                    "pnl": 0.0,
                    "catalysts": ["Manual trader button trigger"]
                }
                trades.append(trade_record)
                self._save_trades_history(trades)
    
                if one_shot_active and self.ai_settings.get("oneShotAiStartTrade"):
                    self.ai_settings["oneShotAiStartTrade"] = False
                    self._save_config()
                    logger.info("[AutoExecutor] [1-SHOT AI MODE] Manual trade placed! Auto-resetting 'oneShotAiStartTrade' back to normal (OFF).")
    
                # Connect with scalp_engine for early profit exits if scalping is enabled
                try:
                    if getattr(scalp_engine, "enabled", False):
                        scalp_engine.register_position(trade_record)
                except Exception as se_err:
                    logger.warning(f"[AutoExecutor] Could not register manual trade with ScalpEngine: {se_err}")
    
                return {"success": True, "trade": trade_record}
    
            if order_res.get("ambiguous"):
                logger.error(
                    f"[AutoExecutor] CRITICAL: Manual trade outcome ambiguous after timeout! "
                    f"Ticker: '{order_res.get('ticker', active_m.get('ticker', ''))}', "
                    f"Client Order ID: '{order_res.get('client_order_id')}'. "
                    f"Error: {order_res.get('error')}. MANUAL VERIFICATION REQUIRED ON KALSHI."
                )
            return order_res


