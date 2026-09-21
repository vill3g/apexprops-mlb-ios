"""
Autonomous 15-Minute Bitcoin Kalshi Execution Engine
Monitors the 15-minute candle countdown, triggers algorithmic execution
on high-conviction Grade A+/A setups, tracks paper/live trades, and computes P&L.
"""

import logging
logger = logging.getLogger(__name__)
import os
import time
import json
import uuid
from typing import Dict, Any, List, Optional
import math
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.btc.kalshi_trader import kalshi_trader
from backend.engine.multi_asset_fetcher import is_market_open, fetch_asset_candles as fetch_candles, get_asset_ticker as get_btc_ticker, get_candle_countdown
from backend.btc.indicators import add_all_indicators
from backend.btc.analyzer import evaluate_next_15m_contract
from backend.btc.pattern_detector import detect_candlestick_patterns
from backend.btc.loss_analyzer import loss_analyzer

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
HISTORY_FILE = os.path.join(DATA_DIR, "trades_history.json")
CONFIG_FILE = os.path.join(DATA_DIR, "trading_config.json")

import threading
# Exit helpers load and save history while retaining the surrounding lock.
# Re-entrant locking prevents those safe nested calls from deadlocking.
_history_lock = threading.RLock()

import tempfile

# Atomic JSON write shared utility — extracted to io_utils for reuse by paper_balance, etc.
from backend.btc.io_utils import atomic_json_write as _atomic_json_write

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


class AutoExecutor:
    def __init__(self, asset: str = "BTC"):
        self.asset = asset
        self.enabled: bool = False
        self.mode: str = "PAPER"  # "PAPER" or "LIVE"
        self.min_conviction: str = "GRADE B SETUP"  # "GRADE A+ SETUP", "GRADE A SETUP", or "GRADE B SETUP"
        self.max_contracts: int = 1
        self.prediction_mode: bool = True
        self.max_daily_risk: float = 25.0
        self.max_daily_trades: int = 10
        self.last_traded_interval: Optional[str] = None
        self.last_check_time: float = 0.0
        self.ai_settings: dict = {}
        self._rollover_lock = threading.Lock()
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
            from backend.btc.trade_db import get_trade_db
            self.trade_db = get_trade_db()
            self.trade_db.import_from_json_if_needed(self._history_file, asset=self.asset)
        except Exception as dbe:
            logger.warning(f"[AutoExecutor] TradeDB init error: {dbe}")
            self.trade_db = None

        self._load_config()


    def set_ai_settings(self, data: dict):
        self.ai_settings = data
        self.ai_settings.pop("maxEntryPriceDollars", None)
        self._save_config()
        return {"status": "ok"}

    def _load_config(self):
        if os.path.exists(self._config_file):
            try:
                with open(self._config_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.enabled = bool(cfg.get("enabled", False))
                    self.mode = cfg.get("mode", "PAPER")
                    self.min_conviction = cfg.get("min_conviction", "GRADE B SETUP")
                    self.max_contracts = int(cfg.get("max_contracts", 1))
                    self.prediction_mode = bool(cfg.get("prediction_mode", True))
                    self.max_daily_risk = float(cfg.get("max_daily_risk", 25.0))
                    self.max_daily_trades = int(cfg.get("max_daily_trades", 10))
                    self.ai_settings = cfg.get("ai_settings") or {}
                    if not isinstance(self.ai_settings, dict):
                        self.ai_settings = {}
                    if "dryRun" not in self.ai_settings:
                        # Safe default: only force dryRun=True if mode is also PAPER
                        # Never silently override an explicit False from saved config
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
                    # Finding 1: Startup safety override
                    if self.mode == "LIVE" and not os.path.exists(self._history_file):
                        logger.warning(
                            f"[AutoExecutor] SAFETY OVERRIDE: Deployment has mode=LIVE but no trades history found for {self.asset}. "
                            "Demoting mode to 'PAPER' and setting enabled=False for safety."
                        )
                        self.mode = "PAPER"
                        self.enabled = False
                        self._save_config()
            except Exception as e:
                logger.error(f"[AutoExecutor] Error loading config: {e}")

    def _save_config(self):
        try:
            _atomic_json_write(self._config_file, {
                "enabled": self.enabled,
                "mode": self.mode,
                "min_conviction": self.min_conviction,
                "max_contracts": self.max_contracts,
                "prediction_mode": self.prediction_mode,
                "max_daily_risk": self.max_daily_risk,
                "max_daily_trades": self.max_daily_trades,
                "ai_settings": self.ai_settings
            })
        except Exception as e:
            logger.error(f"[AutoExecutor] Error saving config: {e}")

    def get_trades_history(self) -> List[Dict[str, Any]]:
        import copy
        with _history_lock:
            trade_db = getattr(self, "trade_db", None)
            if trade_db is not None:
                try:
                    db_trades = trade_db.get_trades(asset=self.asset)
                    if db_trades:
                        self._cached_trades = db_trades
                        if os.path.exists(self._history_file):
                            try:
                                self._cached_trades_mtime = os.path.getmtime(self._history_file)
                            except Exception:
                                pass
                        return copy.deepcopy(db_trades)
                except Exception as dbe:
                    logger.debug(f"[AutoExecutor] TradeDB get_trades fallback to file: {dbe}")

            if os.path.exists(self._history_file):
                try:
                    mtime = os.path.getmtime(self._history_file)
                    if self._cached_trades and self._cached_trades_mtime == mtime:
                        return copy.deepcopy(self._cached_trades)
                    with open(self._history_file, "r", encoding="utf-8") as f:
                        trades = json.load(f)
                        self._cached_trades = trades
                        self._cached_trades_mtime = mtime
                        if trade_db is not None and trades:
                            trade_db.upsert_trades(trades, asset=self.asset)
                        return copy.deepcopy(trades)
                except Exception as e:
                    logger.warning(f"Swallowed exception: {e}")
                    return copy.deepcopy(self._cached_trades) if self._cached_trades else []
        return []

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        trades = self.get_trades_history()
        return trades[-limit:][::-1] if limit else trades[::-1]

    def _save_trades_history(self, trades: List[Dict[str, Any]]):
        try:
            with _history_lock:
                trade_db = getattr(self, "trade_db", None)
                if trade_db is not None:
                    try:
                        trade_db.upsert_trades(trades, asset=self.asset)
                    except Exception as dbe:
                        logger.error(f"[AutoExecutor] TradeDB upsert error: {dbe}")

                _atomic_json_write(self._history_file, trades)
                self._cached_trades = trades
                self._cached_trades_mtime = os.path.getmtime(self._history_file)
        except Exception as e:
            logger.error(f"[AutoExecutor] Error saving trades: {e}")

    def set_enabled(self, enabled: bool) -> Dict[str, Any]:
        self.enabled = enabled
        self._save_config()
        return {"status": "ok", "enabled": self.enabled, "mode": self.mode}

    def set_mode(self, mode: str) -> Dict[str, Any]:
        mode_clean = mode.upper().strip()
        if mode_clean in ["PAPER", "LIVE"]:
            if mode_clean == "LIVE":
                from backend.btc.kalshi_trader import kalshi_trader
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

    def _compute_effective_daily_risk(self, today_trades: list) -> tuple:
        """Returns (today_net_pnl, open_collateral, effective_risk) for a list of
        today's trades already filtered to the current mode. Shared by
        check_risk_budget() and get_status() so pause/block logic never diverges.
        """
        today_net_pnl = sum(float(t.get("pnl", 0.0)) for t in today_trades if t.get("status") in ["SETTLED", "CLOSED"])
        # Also account for realized profits already locked in on still-open trades (partial exits, trailing TP)
        today_net_pnl += sum(float(t.get("realized_pnl", 0.0)) for t in today_trades if t.get("status") == "OPEN" and float(t.get("realized_pnl", 0.0)) != 0.0)
        open_collateral = sum(
            float(t.get("entry_price", 0.50)) * int(t.get("count", 1))
            for t in today_trades
            if t.get("status") in ["OPEN", "PENDING"]
        )
        effective_risk = today_net_pnl - open_collateral
        return today_net_pnl, open_collateral, effective_risk

    def check_risk_budget(self, trades: Optional[List[Dict[str, Any]]] = None) -> Optional[str]:
        """Returns None if trading is allowed, or a human-readable reason string if blocked.

        Enforces today's ET trade count limit (max_daily_trades) and effective risk limit (max_daily_risk),
        where effective risk = settled net PnL minus open trade collateral.
        """
        if trades is None:
            trades = self.get_trades_history()
#         from zoneinfo import ZoneInfo
        today_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
        today_trades = [
            t for t in trades
            if t.get("mode", self.mode).upper() == self.mode
            and str(t.get("timestamp", "")).startswith(today_str)
        ]
        if len(today_trades) >= self.max_daily_trades:
            return f"Max daily trades reached ({len(today_trades)}/{self.max_daily_trades})"

        today_net_pnl, open_collateral, effective_risk = self._compute_effective_daily_risk(today_trades)
        if effective_risk <= -abs(self.max_daily_risk):
            return (
                f"Max daily risk limit reached (Settled PnL: ${today_net_pnl:.2f}, "
                f"Open Collateral: ${open_collateral:.2f}, Effective: ${effective_risk:.2f} <= -${self.max_daily_risk:.2f})"
            )
        return None

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
            except Exception as pos_err:
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
        import copy
        open_pnl_dollars = 0.0
        annotated_open_trades = []
        if active_market and open_trades:
            am_yes_bid = float(active_market.get("yes_bid") or 0.0)
            am_no_bid  = float(active_market.get("no_bid")  or 0.0)
            for t in open_trades:
                t_copy = copy.copy(t)  # shallow copy is enough — we only add top-level keys
                side = str(t_copy.get("side", "YES")).upper()
                entry = float(t_copy.get("entry_price", 0.5))
                count = int(t_copy.get("count", 1))
                current_bid = am_yes_bid if side == "YES" else am_no_bid
                live_pnl = round((current_bid - entry) * count, 4) if current_bid > 0 else 0.0
                t_copy["live_pnl"] = live_pnl
                t_copy["current_bid"] = current_bid
                open_pnl_dollars += live_pnl
                annotated_open_trades.append(t_copy)
        else:
            annotated_open_trades = list(open_trades)

        # Paper Trading Balance Logic
        if self.mode == "PAPER":
            try:
                from backend.btc.paper_balance import load_balance
                bal_dollars = load_balance()
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
            "recent_trades": mode_trades[-15:][::-1],  # latest 15 trades of current mode first
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

    def check_live_calibration_drift(self, min_samples: int = 40, window: int = 100) -> Dict[str, Any]:
        """
        Computes 10-bucket calibration over trailing settled trades (up to window) and checks
        for systematic calibration drift / overconfidence using analyze_calibration_overconfidence.
        If drift is detected, logs a warning and triggers async ml_engine.train(force=True).
        """
        trades = self.get_trades_history()
        settled_trades = [
            t for t in trades
            if t.get("status") in ["SETTLED", "CLOSED"]
            and t.get("result") in ["WIN", "LOSS"]
            and (t.get("predicted_probability") is not None or t.get("probability_percent") is not None)
        ]
        trailing = settled_trades[-window:] if len(settled_trades) > window else settled_trades

        if len(trailing) < min_samples:
            return {
                "status": "insufficient_data",
                "sample_count": len(trailing),
                "min_samples": min_samples,
                "drift_detected": False,
                "calibration_table": [],
            }

        import numpy as np
        preds = []
        actuals = []
        for t in trailing:
            p = t.get("predicted_probability")
            if p is None:
                p = float(t.get("probability_percent", 50)) / 100.0
            else:
                p = float(p)
            p = max(0.0, min(1.0, p))
            y = 1.0 if t.get("result") == "WIN" else 0.0
            preds.append(p)
            actuals.append(y)

        p_arr = np.array(preds)
        y_arr = np.array(actuals)

        calibration_table = []
        for b in range(10):
            low = b * 0.10
            high = (b + 1) * 0.10
            if b == 9:
                mask = (p_arr >= low) & (p_arr <= high)
            else:
                mask = (p_arr >= low) & (p_arr < high)

            count = int(np.sum(mask))
            if count > 0:
                mean_p = float(np.mean(p_arr[mask]))
                realized_wr = float(np.mean(y_arr[mask]))
            else:
                mean_p = float((low + high) / 2.0)
                realized_wr = 0.0

            calibration_table.append({
                "bucket": f"{int(low * 100)}-{int(high * 100)}%",
                "count": count,
                "mean_predicted_prob": round(mean_p, 4),
                "realized_win_rate": round(realized_wr, 4),
                "diff": round(mean_p - realized_wr, 4),
            })

        from backend.btc.backtest import analyze_calibration_overconfidence
        min_bucket = max(3, min_samples // 15)
        drift_detected, reason = analyze_calibration_overconfidence(calibration_table, min_bucket_count=min_bucket)

        if drift_detected:
            logger.warning(f"[AutoExecutor] Live calibration drift detected: {reason}. Triggering ML model retraining.")
            try:
                from backend.btc.ml_engine import get_ml_engine
                ml_eng = get_ml_engine()
                threading.Thread(target=ml_eng.train, kwargs={"force": True}, daemon=True, name="MLDriftRetrainThread").start()
            except Exception as e:
                logger.error(f"[AutoExecutor] Failed to launch drift retraining thread: {e}")

        return {
            "status": "ok",
            "sample_count": len(trailing),
            "drift_detected": drift_detected,
            "reason": reason,
            "calibration_table": calibration_table,
        }

    def check_settlements(self, trades: Optional[List[Dict[str, Any]]] = None):
        """
        Settle completed Kalshi trades from Kalshi's own YES/NO result.

        A candle close is not Kalshi's settlement authority, so it is only kept
        as a legacy fallback for non-Kalshi records that have a valid strike.
        """
        now_ts = time.time()
        if (now_ts - getattr(self, "_last_settlement_check_ts", 0.0)) < 3.0:
            return
        self._last_settlement_check_ts = now_ts

        with _history_lock:
            if trades is None:
                trades = self.get_trades_history()

            modified = False
            newly_settled_count = 0
            settle_candles_df = None
            official_results: Dict[str, Dict[str, Any]] = {}

            for t in trades:
                if t.get("status") != "OPEN":
                    continue

                close_epoch = t.get("close_epoch", 0)
                close_time_str = t.get("interval_close_time") or ""
                if not close_epoch and close_time_str:
                    try:
                        close_epoch = datetime.fromisoformat(close_time_str.replace("Z", "+00:00")).timestamp()
                    except (TypeError, ValueError):
                        continue
                if not close_epoch or now_ts <= float(close_epoch) + 2:
                    continue

                try:
                    ticker = str(t.get("ticker", "")).strip()
                    if ticker and ticker not in official_results:
                        official_results[ticker] = kalshi_trader.get_market_result(ticker)
                    official = official_results.get(ticker, {})
                    official_result = str(official.get("result", "")).upper()

                    if official.get("success") and official_result in {"YES", "NO"}:
                        side = str(t.get("side", "")).upper()
                        entry_price = float(t.get("entry_price", 0.50))
                        count = int(t.get("count", 1))
                        is_win = side == official_result
                        market = official.get("market") or {}
                        settle_price = market.get("settlement_value") or market.get("settlement_value_dollars")
                        try:
                            settle_price = float(settle_price)
                        except (TypeError, ValueError):
                            settle_price = None

                        t["status"] = "SETTLED"
                        t["result"] = "WIN" if is_win else "LOSS"
                        t["official_result"] = official_result
                        t["settlement_source"] = "kalshi_official"
                        t["prediction_correct"] = (not is_win if t.get("is_reverse") else is_win) if t.get("prediction_kind") == "AUTO" else None
                        if not is_win:
                            try:
                                from backend.btc.loss_analyzer import loss_analyzer
                                t["loss_analysis"] = loss_analyzer.diagnose_loss(t)
                            except Exception as ele:
                                logger.warning(f"[AutoExecutor] Loss diagnosis error for {t.get('ticker', t.get('id'))}: {ele}")
                        if settle_price is not None and settle_price > 0:
                            t["settle_price"] = settle_price
                        prior_realized_pnl = float(t.get("realized_pnl", 0.0))
                        settlement_pnl = round(((1.0 - entry_price) * count) if is_win else (-entry_price * count), 4)
                        t["pnl"] = round(prior_realized_pnl + settlement_pnl, 4)
                        t["settlement_pnl"] = settlement_pnl
                        t["settled_at"] = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET")
                        modified = True
                        newly_settled_count += 1

                        if t.get("mode", self.mode).upper() == "PAPER":
                            try:
                                from backend.btc.paper_balance import update_balance
                                update_balance(float(count) if is_win else 0.0)
                            except Exception as ep:
                                logger.info(f"Failed to update paper balance: {ep}")
                        continue

                    # Auto predictions and Kalshi tickers wait for official result, unless it's a synthetic paper trade or past fallback window
                    if (t.get("prediction_kind") == "AUTO" or ticker.startswith("KX")) and not ticker.endswith("_SYNTH"):
                        if now_ts <= float(close_epoch) + 600:
                            continue

                    strike = float(t.get("strike", 0.0) or 0.0)
                    if strike <= 0:
                        continue
                    if settle_candles_df is None:
                        try:
                            settle_candles_df = fetch_candles(self.asset, timeframe="15m", limit=5)
                        except Exception as ce:
                            logger.debug(f"[AutoExecutor] Legacy settlement data unavailable for {ticker}: {ce}")
                            settle_candles_df = None
                    if settle_candles_df is None or len(settle_candles_df) < 2:
                        continue
                    settle_price = float(settle_candles_df.iloc[-2]["close"])
                    side = str(t.get("side", "")).upper()
                    entry_price = float(t.get("entry_price", 0.50))
                    count = int(t.get("count", 1))
                    is_win = (side == "YES" and settle_price >= strike) or (side == "NO" and settle_price < strike)
                    t.update({
                        "status": "SETTLED", "result": "WIN" if is_win else "LOSS",
                        "settlement_source": "legacy_exchange_candle", "settle_price": settle_price,
                        "pnl": round(((1.0 - entry_price) * count) if is_win else (-entry_price * count), 4),
                        "settled_at": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                    })
                    modified = True
                    newly_settled_count += 1
                except Exception as e:
                    logger.error(f"[AutoExecutor] Error checking settlement for trade {t.get('id')}: {e}")

            if modified:
                try:
                    self._save_trades_history(trades)
                    self._settled_since_drift_check += newly_settled_count
                    if self._settled_since_drift_check >= 50:
                        self._settled_since_drift_check = 0
                        try:
                            self.check_live_calibration_drift()
                        except Exception as cde:
                            logger.warning(f"[AutoExecutor] Scheduled calibration drift check failed: {cde}")

                    # Trigger background retrain asynchronously in a daemon thread so it never blocks API requests
                    try:
                        from backend.btc.ml_engine import get_ml_engine
                        ml_eng = get_ml_engine()
                        threading.Thread(target=ml_eng.train, daemon=True, name="MLRetrainThread").start()
                    except Exception as e:
                        logger.warning(f"[AutoExecutor] Post-settlement ML retrain launch failed: {e}")
                except Exception as e:
                    logger.error(f"[AutoExecutor] Error saving trades in check_settlements: {e}")

        # Hook: RL Shadow Sandbox settlements
        try:
            from backend.btc.shadow_executor import update_shadow_settlements
            update_shadow_settlements(kalshi_trader)
        except Exception as e:
            logger.error(f"[ShadowExecutor Hook] Error: {e}")

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
            if (now - self.last_check_time) < 4.0:
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
                window_valid = sec_left > 30  # Allows mid-candle evaluation
            else:
                window_valid = is_prediction_window if self.prediction_mode else is_rollover_window

            if not window_valid:
                return None

            # Fetch active Kalshi KXBTC15M market (require at least 45s before close)
            active_m = kalshi_trader.get_active_15m_market(series_ticker=f"KX{self.asset}15M", allow_synthetic=(self.mode == "PAPER"), min_seconds_left=45)
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
            if effective_style == "AUTO":
                curr = df_ind.iloc[-1] if len(df_ind) > 0 else None
                if curr is not None:
                    try:
                        vr_raw = curr.get("vol_ratio", 1.0)
                        vol_ratio = float(vr_raw) if vr_raw is not None and not pd.isna(vr_raw) else 1.0
                    except (ValueError, TypeError):
                        vol_ratio = 1.0
                    try:
                        bb_raw = curr.get("bb_bandwidth", 1.0)
                        bb_width = float(bb_raw) if bb_raw is not None and not pd.isna(bb_raw) else 1.0
                    except (ValueError, TypeError):
                        bb_width = 1.0
                        
                    adx = float(curr.get("adx", 20.0))
                    
                    try:
                        from backend.btc.liquidation_stream import get_liquidation_imbalance
                        liq = get_liquidation_imbalance()
                        liq_total = liq["short_liquidations_usd"] + liq["long_liquidations_usd"]
                    except Exception:
                        liq_total = 0.0

                    if liq_total > 1_500_000 or (vol_ratio > 1.5 and adx > 25.0):
                        effective_style = "MOMENTUM_SURFER"
                        logger.info(f"[AutoExecutor] AUTO Mode routed to MOMENTUM_SURFER (Vol: {vol_ratio:.2f}, ADX: {adx:.1f}, Liq: ${liq_total/1e6:.1f}M)")
                    elif vol_ratio < 0.85 and bb_width < 0.015 and adx < 20.0:
                        effective_style = "CHOP"
                        logger.info(f"[AutoExecutor] AUTO Mode routed to CHOP (Vol: {vol_ratio:.2f}, BBW: {bb_width:.4f}, ADX: {adx:.1f})")
                    elif vol_ratio > 1.1:
                        effective_style = "AMBUSH"
                        logger.info(f"[AutoExecutor] AUTO Mode routed to AMBUSH (Vol: {vol_ratio:.2f}, ADX: {adx:.1f})")
                    else:
                        effective_style = "SNIPER"
                        logger.info(f"[AutoExecutor] AUTO Mode routed to SNIPER (Vol: {vol_ratio:.2f}, ADX: {adx:.1f})")
                else:
                    effective_style = "SNIPER"

            # Inject historical market intervals directly into the ML Engine to train it instantly
            try:
                from backend.btc.ml_engine import get_ml_engine
                import os
                data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
                ml_engine = get_ml_engine(data_dir, effective_style)
                if not ml_engine.is_trained:
                    from backend.btc.data_fetcher import fetch_15m_candles_history, fetch_1m_candles_history
                    
                    if effective_style == "MOMENTUM_SURFER":
                        hist_df = fetch_1m_candles_history(days=15)
                    else:
                        hist_df = fetch_15m_candles_history(days=60)
                        
                    hist_df_ind = add_all_indicators(hist_df)
                    ml_engine.self_train_on_historical_market(hist_df_ind)
            except Exception as e:
                logger.error(f"[AutoExecutor] Failed to self-train ML Engine: {e}")

            # Detect advanced chart patterns (triangles, flags, head & shoulders)
            patterns = []
            if effective_style != "MOMENTUM_SURFER":
                try:
                    patterns = detect_candlestick_patterns(df_ind)
                except Exception as _pat_err:
                    logger.debug(f"[AutoExecutor] Pattern detector error: {_pat_err}")

            if effective_style == "CHOP":
                try:
                    from backend.btc.chop_engine import evaluate_chop_contract
                    forecast = evaluate_chop_contract(df_ind, target_price=strike, kalshi_m=active_m)
                except Exception as chop_err:
                    logger.error(
                        f"[AutoExecutor] chop_engine unavailable ({chop_err}); "
                        f"falling back to standard SNIPER evaluation for this cycle."
                    )
                    forecast = evaluate_next_15m_contract(
                        df_ind, target_price=strike, patterns=patterns, kalshi_m=active_m, trading_style="SNIPER"
                    )
            else:
                forecast = evaluate_next_15m_contract(
                    df_ind, target_price=strike, patterns=patterns, kalshi_m=active_m, trading_style=effective_style
                )

            # Hook: RL Shadow Sandbox execution
            try:
                from backend.btc.shadow_executor import execute_shadow_trade
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
                logger.info(f"[AutoExecutor] Strike Pin Risk active (price within $15 of strike target in low volatility). Sitting out to protect win rate.")
                return None

            if (one_shot_ai or ignore_pass):
                # 100% AI Prediction mode (until toggled off if ignore_pass, or 1-shot if one_shot_ai)
                # Use raw unmolested ML probability directly from the model
                ai_model_prob = raw_ml_prob
                if ai_model_prob != 0.50:
                    direction = "ABOVE" if ai_model_prob > 0.50 else "BELOW"
                    raw_score = max(51.0, ai_model_prob * 100.0) if ai_model_prob > 0.50 else max(51.0, (1.0 - ai_model_prob) * 100.0)
                else:
                    direction = pre_gate_dir if pre_gate_dir in ["ABOVE", "BELOW"] else "ABOVE"
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

            # Map signal to Kalshi contract side
            # "ABOVE" -> buy YES (anticipating price >= strike)
            # "BELOW" -> buy NO (anticipating price < strike)
            side = "yes" if direction == "ABOVE" else "no"
            market_price = active_m.get("yes_ask" if side == "yes" else "no_ask") or 0.50

            # Determine affordable contract count for live or paper
        
            # ML Settings Overrides: Use maxCap to size position
            max_cap = float(self.ai_settings.get("maxCap", 0.0))
            unit_price_est = min(0.99, max(0.01, float(market_price) + 0.04))
        
            # AUDIT FIX #3: Hard ceiling on contracts to prevent black-swan order sizes
            ABSOLUTE_MAX_CONTRACTS = 999999

            if max_cap > 0:
                contracts_to_buy = int(max_cap // unit_price_est)
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
            

            if self.mode == "LIVE":

                bal_res = kalshi_trader.get_balance()
                if bal_res.get("success", False):
                    avail_bal = float(bal_res.get("balance_dollars", 0.0))
                    unit_price = min(0.99, max(0.01, float(market_price) + 0.04))
                    if unit_price > 0 and avail_bal < (unit_price * contracts_to_buy):
                        affordable = int(avail_bal // unit_price)
                        contracts_to_buy = affordable
            
            if contracts_to_buy < 1:
                logger.warning(f"Insufficient balance to execute trade. Skipping.")
                return None

            slippage_buffer = float(self.ai_settings.get("slippageBufferDollars", self.ai_settings.get("slippageBufferCents", 0.04)))

            # Execute Order (Paper or Live)
            order_res = kalshi_trader.place_order(
                ticker=current_interval_id,
                side=side,
                count=contracts_to_buy,
                limit_price_dollars=market_price,
                dry_run=dry_run,
                slippage_buffer_dollars=slippage_buffer
            )

            if order_res.get("success", False):
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
                        from backend.btc.paper_balance import update_balance
                        update_balance(-fill_cost)
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
                    from backend.btc.scalp_engine import scalp_engine
                    if getattr(scalp_engine, "enabled", False):
                        scalp_engine.register_position(trade_record)
                except Exception as se_err:
                    logger.warning(f"[AutoExecutor] Could not register trade with ScalpEngine: {se_err}")

            else:
                if order_res.get("ambiguous"):
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

    def execute_manual_trade(self, direction: str) -> Dict[str, Any]:
        self._load_config()
        """
        Enables user to click 1-click execution for the current interval directly from the UI.
        """
        dir_clean = str(direction or "").upper().strip()
        one_shot_active = bool(self.ai_settings.get("oneShotAiStartTrade", False)) or dir_clean in ["AI_START", "AI", "AUTO"]

        # Finding 2: Enforce shared daily risk budget on manual trades
        risk_blocked_reason = self.check_risk_budget()
        if risk_blocked_reason:
            logger.info(f"[AutoExecutor] Manual trade blocked: {risk_blocked_reason}")
            return {"success": False, "error": risk_blocked_reason}

        active_m = kalshi_trader.get_active_15m_market(series_ticker=f"KX{self.asset}15M", allow_synthetic=(self.mode == "PAPER"), min_seconds_left=30)
        if not active_m:
            return {"success": False, "error": f"No active KX{self.asset}15M market found (>30s before expiration required)."}

        if dir_clean in ["AI_START", "AI", "AUTO"]:
            try:
                df = fetch_candles(self.asset, timeframe="15m", limit=1000)
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
                    dir_clean = "ABOVE" if ml_prob >= 0.50 else "BELOW"
                    logger.warning(f"[AutoExecutor] AI_START: forecast direction was '{forecast_dir}', falling back to ml_prob={ml_prob:.3f} -> {dir_clean}")
            except Exception as _ai_err:
                logger.error(f"[AutoExecutor] Error resolving AI start direction: {_ai_err}")
                dir_clean = "ABOVE"

        if dir_clean not in ["ABOVE", "BELOW"]:
            return {"success": False, "error": f"Invalid trade direction: '{direction}'. Must be 'ABOVE' or 'BELOW'."}

        side = "yes" if dir_clean == "ABOVE" else "no"
        market_price = active_m.get("yes_ask" if side == "yes" else "no_ask") or 0.50

        # Determine affordable contract count for live or paper
        
        # ML Settings Overrides: Use maxCap to size position
        max_cap = float(self.ai_settings.get("maxCap", 0.0))
        unit_price_est = min(0.99, max(0.01, float(market_price) + 0.04))
        
        ABSOLUTE_MAX_CONTRACTS = 999999
        if max_cap > 0:
            contracts_to_buy = int(max_cap // unit_price_est)
            if contracts_to_buy < 1:
                contracts_to_buy = 1
        else:
            contracts_to_buy = self.max_contracts

        contracts_to_buy = min(contracts_to_buy, ABSOLUTE_MAX_CONTRACTS)

        # 2. Dry Run
        dry_run = (self.mode == "PAPER")
        if self.ai_settings.get("dryRun", False):
            dry_run = True

        if self.mode == "LIVE":

            bal_res = kalshi_trader.get_balance()
            if bal_res.get("success", False):
                avail_bal = float(bal_res.get("balance_dollars", 0.0))
                unit_price = min(0.99, max(0.01, float(market_price) + 0.04))
                if unit_price > 0 and avail_bal < (unit_price * contracts_to_buy):
                    affordable = int(avail_bal // unit_price)
                    contracts_to_buy = affordable
        
        if contracts_to_buy < 1:
            logger.warning(f"Insufficient balance to execute trade. Skipping.")
            return None

        slippage_buffer = float(self.ai_settings.get("slippageBufferDollars", self.ai_settings.get("slippageBufferCents", 0.04)))

        order_res = kalshi_trader.place_order(
            ticker=active_m.get("ticker", ""),
            side=side,
            count=contracts_to_buy,
            limit_price_dollars=market_price,
            dry_run=dry_run,
            slippage_buffer_dollars=slippage_buffer
        )

        if order_res.get("success", False):
            # H1 & H2: Record actual fill metrics and fix paper balance cost key
            fill_price = float(order_res.get("filled_price", market_price))
            fill_count = float(order_res.get("count", contracts_to_buy))
            fill_cost = float(order_res.get("total_cost", round(fill_price * fill_count, 4)))

            if self.mode == "PAPER":
                try:
                    from backend.btc.paper_balance import update_balance
                    update_balance(-fill_cost)
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
                from backend.btc.data_fetcher import get_live_15m_target_data
                from backend.engine.multi_asset_fetcher import is_market_open, get_asset_ticker
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
                from backend.btc.scalp_engine import scalp_engine
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

    def _exit_open_trade(self, trade: Dict[str, Any], reason: str, estimated_exit_price: Optional[float] = None) -> Dict[str, Any]:
        """Close a recorded position at its current Kalshi bid.

        Paper trades use the same public bid as a simulated exit (or estimated_exit_price
        if off-hours/synthetic). Live trades submit a reduce-only IOC order, so a failed
        or unfilled order never changes the local trade record.
        """
        side = str(trade.get("side", "")).upper().strip()
        ticker = str(trade.get("ticker", "")).strip()
        try:
            count = float(trade.get("count", 0))
            entry_price = float(trade.get("entry_price", 0))
        except (TypeError, ValueError):
            return {"success": False, "error": "Trade has invalid price or contract count."}
        if side not in {"YES", "NO"} or not ticker or count <= 0:
            return {"success": False, "error": "Trade is missing a valid ticker, side, or contract count."}

        mode = str(trade.get("mode", self.mode)).upper()
        is_sim = str(trade.get("id", "")).startswith("sim_") or (mode == "PAPER")
        exit_res = kalshi_trader.close_position(
            ticker=ticker,
            purchased_side=side,
            count=count,
            dry_run=is_sim,
            estimated_exit_price=estimated_exit_price,
        )
        if not exit_res.get("success"):
            if exit_res.get("ambiguous"):
                logger.error(
                    f"[AutoExecutor] CRITICAL: Position exit outcome ambiguous after timeout! "
                    f"Trade ID: '{trade.get('id')}', Ticker: '{ticker}', "
                    f"Client Order ID: '{exit_res.get('client_order_id')}'. "
                    f"Error: {exit_res.get('error')}. MANUAL VERIFICATION REQUIRED ON KALSHI."
                )
            return exit_res

        filled_count = min(count, float(exit_res.get("filled_count", 0) or 0))
        exit_price = float(exit_res.get("exit_price", 0) or 0)
        fee_paid = float(exit_res.get("fee_paid", 0) or 0)
        if filled_count <= 0 or not 0 < exit_price < 1:
            return {"success": False, "error": "Exit returned no valid fill; the trade remains open."}

        previous_realized = float(trade.get("realized_pnl", 0) or 0)
        exit_pnl = round((exit_price - entry_price) * filled_count - fee_paid, 4)
        realized_pnl = round(previous_realized + exit_pnl, 4)
        remaining_count = max(0.0, round(count - filled_count, 4))
        closed_at = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET")

        trade["last_exit_price"] = exit_price
        trade["exit_fee_paid"] = round(float(trade.get("exit_fee_paid", 0) or 0) + fee_paid, 4)
        trade["exit_reason"] = reason
        trade["exit_source"] = exit_res.get("source", "kalshi_exit")
        trade["realized_pnl"] = realized_pnl
        trade["pnl"] = realized_pnl
        trade.setdefault("partial_exits", []).append({
            "time": closed_at,
            "count": filled_count,
            "price": exit_price,
            "fee_paid": fee_paid,
            "pnl": exit_pnl,
            "source": exit_res.get("source", "kalshi_exit"),
        })

        if mode == "PAPER":
            try:
                from backend.btc.paper_balance import update_balance
                update_balance(exit_price * filled_count)
            except Exception as ep:
                logger.info(f"Failed to update paper balance: {ep}")

        if remaining_count <= 0:
            trade["status"] = "CLOSED"
            trade["result"] = "CLOSED_WIN" if realized_pnl > 0 else ("CLOSED_LOSS" if realized_pnl < 0 else "CLOSED_FLAT")
            trade["exit_price"] = exit_price
            trade["closed_at"] = closed_at
        else:
            trade["count"] = remaining_count
            trade["cost"] = round(entry_price * remaining_count, 4)
            trade["status"] = "OPEN"
            trade["result"] = "PARTIAL_EXIT"

        return {
            "success": True,
            "trade_id": trade.get("id"),
            "filled_count": filled_count,
            "remaining_count": remaining_count,
            "pnl": realized_pnl,
            "closed": remaining_count <= 0,
        }

    def close_specific_trade(self, trade_id: str, reason: str = "SCALP", estimated_exit_price: Optional[float] = None) -> Dict[str, Any]:
        """Close one tracked trade at its current contract bid."""
        with _history_lock:
            trades = self.get_trades_history()
            for trade in trades:
                if trade.get("id") == trade_id and trade.get("status") == "OPEN":
                    result = self._exit_open_trade(trade, reason, estimated_exit_price=estimated_exit_price)
                    if not result.get("success"):
                        return result
                    self._save_trades_history(trades)
                    try:
                        from backend.btc.scalp_engine import scalp_engine
                        with scalp_engine._trade_lock:
                            if hasattr(scalp_engine, "_active_positions") and trade_id in scalp_engine._active_positions:
                                del scalp_engine._active_positions[trade_id]
                            if scalp_engine._active_trade and scalp_engine._active_trade.get("id") == trade_id:
                                scalp_engine._active_trade.clear()
                    except Exception as e:
                        logger.warning(f"Swallowed exception: {e}")
                        pass
                    return result
        return {"success": False, "error": f"Trade {trade_id} not found or not open"}

    def close_open_trades(self) -> Dict[str, Any]:
        """Close each open trade at its current contract bid.

        Unlike the prior implementation, live trades are only marked closed
        after their reduce-only Kalshi order receives a fill.
        """
        with _history_lock:
            trades = self.get_trades_history()
            open_trades = [trade for trade in trades if trade.get("status") == "OPEN"]
            if not open_trades:
                return {"success": False, "error": "No open trades to close."}

            completed = 0
            partial = 0
            realized_pnl = 0.0
            failures = []
            for trade in open_trades:
                # Dynamic realistic contract price estimation for paper/simulated fallback
                strike = float(trade.get("strike", 0.0) or 0.0)
                side = str(trade.get("side", "YES")).upper()
                est_exit = None
                if strike > 0:
                    try:
                        from backend.engine.multi_asset_fetcher import get_asset_ticker as get_btc_ticker
                        spot = float(get_btc_ticker(self.asset).get("price", 0.0))
                        if spot > 0:
                            diff = (spot - strike) if side == "YES" else (strike - spot)
                            import math
                            prob = 1.0 / (1.0 + math.exp(-diff / 150.0))
                            est_exit = round(max(0.10, min(0.90, prob)), 4)
                    except Exception as e:
                        logger.warning(f"Swallowed exception: {e}")
                        pass

                result = self._exit_open_trade(trade, "MANUAL_CLOSE", estimated_exit_price=est_exit)
                if not result.get("success"):
                    failures.append({"trade_id": trade.get("id"), "error": result.get("error", "Close failed.")})
                    continue
                realized_pnl += float(result.get("pnl", 0) or 0)
                if result.get("closed"):
                    completed += 1
                else:
                    partial += 1

            if completed or partial:
                self._save_trades_history(trades)

        message = f"Closed {completed} position(s)"
        if partial:
            message += f"; {partial} partially filled"
        if failures:
            message += f"; {len(failures)} left open"
        return {
            "success": bool(completed or partial),
            "closed_count": completed,
            "partial_count": partial,
            "realized_pnl": round(realized_pnl, 2),
            "failures": failures,
            "message": f"{message} (realized P&L: ${realized_pnl:+.2f})",
        }

    def check_active_trades_stop_and_reversal(self) -> None:
        """
        Evaluates all open positions for:
        Option 1: Dynamic Early Stop-Loss (Bailout Guard)
          - If spot BTC moves against the strike target by >= stopLossMoveDollars within stopLossMaxMinutes,
            immediately exit early at executable market bid to rescue remaining contract capital.
        Option 2: Position Reversal (Selective Flip)
          - If stopped out and positionReversal is enabled, selectively enter the opposite contract
            if time remaining >= reversalMinMinutesLeft, opposite ask <= reversalMaxPriceCents,
            and confidence >= reversalMinConfidence.
        """
        dynamic_stop_enabled = bool(self.ai_settings.get("dynamicStopLoss", True))
        position_reversal_enabled = bool(self.ai_settings.get("positionReversal", False))
        take_profit_enabled = bool(self.ai_settings.get("takeProfitEnabled", True))
        take_profit_percent = float(self.ai_settings.get("takeProfitPercent", 50.0))

        if not dynamic_stop_enabled and not position_reversal_enabled and not take_profit_enabled:
            return

        trades = self.get_trades_history()
        open_trades = [t for t in trades if t.get("status") == "OPEN"]
        if not open_trades:
            return

        from backend.engine.multi_asset_fetcher import get_asset_ticker as get_btc_ticker
        try:
            ticker_data = get_btc_ticker(self.asset)
            spot_price = float(ticker_data.get("price", 0.0) or 0.0)
        except Exception as te:
            logger.debug(f"[AutoExecutor] Could not fetch spot price for stop/reversal check: {te}")
            return

        if spot_price <= 0:
            return

        stop_loss_move = float(self.ai_settings.get("stopLossMoveDollars", 140.0))
        atr_multiplier = float(self.ai_settings.get("atrStopMultiplier", 0.75))
        try:
            from backend.btc.indicators import compute_atr
            recent_candles = fetch_candles(self.asset, timeframe="15m", limit=30)
            if recent_candles is not None and len(recent_candles) >= 14:
                atr_series = compute_atr(recent_candles)
                atr_val = float(atr_series.iloc[-1])
                if atr_val > 0:
                    stop_loss_move = max(stop_loss_move, atr_val * atr_multiplier)
        except Exception:
            pass
        stop_loss_max_minutes = float(self.ai_settings.get("stopLossMaxMinutes", 8.0))
        reversal_max_price = float(self.ai_settings.get("reversalMaxPriceCents", 65.0)) / 100.0
        reversal_min_minutes = float(self.ai_settings.get("reversalMinMinutesLeft", 6.0))
        reversal_min_conf = float(self.ai_settings.get("reversalMinConfidence", 75.0))

        now = time.time()
        for trade in open_trades:
            trade_id = trade.get("id")
            if not trade_id:
                continue
            side = str(trade.get("side", "")).upper()
            strike = float(trade.get("strike", 0.0) or 0.0)
            entry_price = float(trade.get("entry_price", 0.50))
            btc_entry = float(trade.get("btc_price_at_entry") or trade.get("market_snapshot", {}).get("price") or spot_price)
            close_epoch = float(trade.get("close_epoch", 0.0))

            if close_epoch > 0:
                time_remaining_sec = max(0.0, close_epoch - now)
                time_elapsed_sec = max(0.0, 900.0 - time_remaining_sec)
            else:
                time_remaining_sec = 900.0
                time_elapsed_sec = 0.0

            minutes_elapsed = time_elapsed_sec / 60.0
            minutes_remaining = time_remaining_sec / 60.0

            if take_profit_enabled and minutes_remaining >= 1.0:
                ticker = trade.get("ticker")
                bid_price = 0.0
                if ticker and not ticker.endswith("_SYNTH") and self.mode == "LIVE":
                    try:
                        from backend.btc.kalshi_trader import kalshi_trader
                        quote = kalshi_trader.get_market_quote(ticker)
                        if quote.get("success"):
                            bid_price = float(quote.get("yes_bid", 0.0)) if side == "YES" else float(quote.get("no_bid", 0.0))
                    except Exception as e:
                        logger.warning(f"[AutoExecutor] Take profit quote fetch failed: {e}")
                elif self.mode == "PAPER":
                    # Paper trading: Use live Kalshi public orderbook if available, or realistic spot-based delta model
                    if ticker and not ticker.endswith("_SYNTH"):
                        try:
                            from backend.btc.kalshi_trader import kalshi_trader
                            quote = kalshi_trader.get_market_quote(ticker)
                            if quote.get("success"):
                                bid_price = float(quote.get("yes_bid", 0.0)) if side == "YES" else float(quote.get("no_bid", 0.0))
                        except Exception:
                            pass
                    if bid_price <= 0.0 and strike > 0:
                        import math
                        diff = (spot_price - strike) if side == "YES" else (strike - spot_price)
                        prob = 1.0 / (1.0 + math.exp(-diff / 150.0))
                        bid_price = round(max(0.05, min(0.95, prob)), 4)

                if entry_price > 0 and bid_price > 0:
                    try:
                        profit_pct = ((bid_price - entry_price) / entry_price) * 100.0
                        
                        # Track Max Seen Bid for Trailing Stop
                        max_seen_bid = float(trade.get("max_seen_bid", entry_price))
                        if bid_price > max_seen_bid:
                            # C1 FIX: Do NOT save the detached snapshot. Re-fetch fresh data under lock.
                            with _history_lock:
                                fresh_trades = self.get_trades_history()
                                for ft in fresh_trades:
                                    if ft.get("id") == trade_id:
                                        ft["max_seen_bid"] = bid_price
                                        break
                                self._save_trades_history(fresh_trades)
                            trade["max_seen_bid"] = bid_price
                            max_seen_bid = bid_price

                        max_seen_profit_pct = ((max_seen_bid - entry_price) / entry_price) * 100.0

                        # 1. Hard Take-Profit Check
                        if profit_pct >= take_profit_percent:
                            logger.info(
                                f"[AutoExecutor] TAKE-PROFIT TRIGGERED for {trade_id} ({side}): "
                                f"Current bid ${bid_price:.2f} is up {profit_pct:.1f}% from entry ${entry_price:.2f} "
                                f"(Target: {take_profit_percent}%)."
                            )
                            close_res = self.close_specific_trade(trade_id, reason="TAKE_PROFIT", estimated_exit_price=bid_price)
                            if close_res.get("success"):
                                logger.info(f"[AutoExecutor] Take profit executed for {trade_id}; realized P&L ${close_res.get('pnl', 0):.2f}")
                                self._attempt_profit_reentry(trade, minutes_remaining, spot_price)
                                continue

                        # 2. Dynamic Trailing Profit Stop (Locks in gains if they drop from peak)
                        # If the trade was ever up >35% (e.g. $100+ on a $250 size), activate a tight 12% trailing floor
                        if max_seen_profit_pct >= 35.0:
                            # We trail the max seen bid by 12 cents or 12%, whichever tightens first
                            trail_threshold = max(max_seen_bid - 0.12, max_seen_bid * 0.88)
                            
                            # Ensure we don't accidentally trail into a loss
                            trail_threshold = max(trail_threshold, entry_price * 1.10) # Minimum 10% profit secured

                            if bid_price <= trail_threshold:
                                logger.info(
                                    f"[AutoExecutor] DYNAMIC TRAILING PROFIT TRIGGERED for {trade_id} ({side}): "
                                    f"Max bid was ${max_seen_bid:.2f} (+{max_seen_profit_pct:.1f}%), now dropped to ${bid_price:.2f}. Securing gains."
                                )
                                close_res = self.close_specific_trade(trade_id, reason="TRAILING_TAKE_PROFIT", estimated_exit_price=bid_price)
                                if close_res.get("success"):
                                    logger.info(f"[AutoExecutor] Trailing profit executed for {trade_id}; realized P&L ${close_res.get('pnl', 0):.2f}")
                                    self._attempt_profit_reentry(trade, minutes_remaining, spot_price)
                                    continue
                                    
                        # 3. Contract Price Stop Loss
                        stop_loss_pct = float(self.ai_settings.get("stopLossPercent", 50.0))
                        if profit_pct <= -stop_loss_pct:
                            logger.info(
                                f"[AutoExecutor] CONTRACT STOP-LOSS TRIGGERED for {trade_id} ({side}): "
                                f"Current bid ${bid_price:.2f} is down {abs(profit_pct):.1f}% from entry ${entry_price:.2f} "
                                f"(Target: {stop_loss_pct}%)."
                            )
                            close_res = self.close_specific_trade(trade_id, reason="CONTRACT_STOP_LOSS", estimated_exit_price=bid_price)
                            if close_res.get("success"):
                                logger.info(f"[AutoExecutor] Contract stop loss executed for {trade_id}; realized P&L ${close_res.get('pnl', 0):.2f}")
                                continue
                    except Exception as e:
                        logger.warning(f"[AutoExecutor] Take profit check failed: {e}")

            if dynamic_stop_enabled:
                # Early stop window check: first stop_loss_max_minutes and at least 90 seconds left
                if minutes_elapsed <= stop_loss_max_minutes and minutes_remaining >= 1.5:
                    is_adverse = False
                    deficit = 0.0

                    if strike > 0:
                        if side == "YES" and spot_price < strike:
                            deficit = strike - spot_price
                            if deficit >= stop_loss_move:
                                is_adverse = True
                        elif side == "NO" and spot_price >= strike:
                            deficit = spot_price - strike
                            if deficit >= stop_loss_move:
                                is_adverse = True
                    else:
                        if side == "YES" and spot_price < btc_entry:
                            deficit = btc_entry - spot_price
                            if deficit >= stop_loss_move:
                                is_adverse = True
                        elif side == "NO" and spot_price >= btc_entry:
                            deficit = spot_price - btc_entry
                            if deficit >= stop_loss_move:
                                is_adverse = True

                    if is_adverse:
                        logger.info(
                            f"[AutoExecutor] DYNAMIC STOP-LOSS TRIGGERED for {trade_id} ({side}): "
                            f"Spot ${spot_price:,.2f} adverse deficit ${deficit:.2f} >= ${stop_loss_move:.2f} "
                            f"at {minutes_elapsed:.1f}m elapsed ({minutes_remaining:.1f}m left)."
                        )
                        # Realistic salvage exit price for simulation / paper fallback
                        est_exit = round(max(0.10, min(0.40, entry_price - 0.25)), 4)
                        close_res = self.close_specific_trade(trade_id, reason="DYNAMIC_STOP_LOSS", estimated_exit_price=est_exit)
                        if close_res.get("success"):
                            logger.info(f"[AutoExecutor] Early stop executed for {trade_id}; realized P&L ${close_res.get('pnl', 0):.2f}")
                            if position_reversal_enabled and not trade.get("is_reversal"):
                                self._attempt_position_reversal(
                                    stopped_trade=trade,
                                    spot_price=spot_price,
                                    minutes_remaining=minutes_remaining,
                                    reversal_max_price=reversal_max_price,
                                    reversal_min_minutes=reversal_min_minutes,
                                    reversal_min_conf=reversal_min_conf
                                )

    def _attempt_position_reversal(
        self,
        stopped_trade: Dict[str, Any],
        spot_price: float,
        minutes_remaining: float,
        reversal_max_price: float,
        reversal_min_minutes: float,
        reversal_min_conf: float
    ) -> Optional[Dict[str, Any]]:
        """
        Executes a position reversal (flip) following an early stop-loss exit.
        Enforces strict safety guardrails:
        1. Time: minutes_remaining >= reversal_min_minutes.
        2. Single reversal per interval (no recursive flips).
        3. Price: opposite contract ask <= reversal_max_price (favorable risk/reward).
        4. Confidence: reversal direction confidence >= reversal_min_conf.
        """
        stopped_side = str(stopped_trade.get("side", "")).upper()
        opposite_side = "NO" if stopped_side == "YES" else "YES"
        ticker = stopped_trade.get("ticker", "")

        # Guardrail 1: Time remaining
        if minutes_remaining < reversal_min_minutes:
            logger.info(
                f"[AutoExecutor] Reversal rejected: {minutes_remaining:.1f}m remaining "
                f"< min required {reversal_min_minutes:.1f}m."
            )
            return None

        # Guardrail 2: Max 1 reversal per interval
        interval_trades = self.get_trades_history()
        already_reversed = any(
            t.get("ticker") == ticker and t.get("is_reversal")
            for t in interval_trades
        )
        if already_reversed:
            logger.info(f"[AutoExecutor] Reversal rejected: Interval {ticker} already completed a reversal trade.")
            return None

        # Guardrail 3: Market quote on opposite contract
        opposite_ask = 0.50
        active_m = kalshi_trader.get_active_15m_market(series_ticker=f"KX{self.asset}15M", allow_synthetic=(self.mode == "PAPER"))
        if active_m and (active_m.get("ticker") == ticker or not ticker):
            if opposite_side == "YES":
                opposite_ask = float(active_m.get("yes_ask", 0.50) or 0.50)
            else:
                opposite_ask = float(active_m.get("no_ask", 0.50) or 0.50)

        if opposite_ask > reversal_max_price:
            logger.info(
                f"[AutoExecutor] Reversal rejected: Opposite {opposite_side} ask ${opposite_ask:.2f} "
                f"> max allowed ${reversal_max_price:.2f}."
            )
            return None

        # Guardrail 4: Confidence & Directional Momentum
        # The model must (a) recommend the opposite direction and (b) clear the confidence bar.
        conf = None
        model_direction = None
        try:
            from backend.engine.multi_asset_fetcher import is_market_open, fetch_asset_candles as fetch_candles, get_asset_ticker as get_btc_ticker
            from backend.btc.indicators import add_all_indicators
            from backend.btc.analyzer import evaluate_next_15m_contract
            strike = float(stopped_trade.get("strike", 0.0) or (active_m.get("strike_price", 0.0) if active_m else 0.0))
            df_c = fetch_candles(self.asset, timeframe="15m", limit=30)
            if df_c is not None and not df_c.empty:
                df_ind = add_all_indicators(df_c)
                eval_res = evaluate_next_15m_contract(df_ind, target_price=strike, kalshi_m=active_m)
                conf = float(eval_res.get("probability_percent", 0.0))
                model_direction = normalize_prediction_direction(eval_res.get("recommendation", ""))
            # else: conf stays None → rejected below
        except Exception as eg4:
            logger.warning(f"[AutoExecutor] Reversal Guardrail 4 evaluation failed: {eg4}")
            # conf stays None → rejected below

        if conf is None:
            logger.info("[AutoExecutor] Reversal rejected: Could not evaluate momentum confidence (no candle data or error).")
            return None

        # normalize_prediction_direction maps YES→ABOVE and NO→BELOW; compute expected
        # from opposite_side the same way and compare.
        expected_direction = normalize_prediction_direction(opposite_side)
        if model_direction != expected_direction:
            logger.info(
                f"[AutoExecutor] Reversal rejected: Model recommends {model_direction!r}, "
                f"not the required opposite direction {expected_direction!r} (opposite of {stopped_side})."
            )
            return None

        if conf < reversal_min_conf:
            logger.info(
                f"[AutoExecutor] Reversal rejected: Momentum confidence {conf:.1f}% "
                f"< min required {reversal_min_conf:.1f}%."
            )
            return None

        # All guardrails passed! Place reversal order
        logger.info(
            f"[AutoExecutor] Executing POSITION REVERSAL: Flipping {stopped_side} -> {opposite_side} "
            f"on {ticker} @ ~${opposite_ask:.2f} ({minutes_remaining:.1f}m left, conf {conf:.1f}%)"
        )

        count = min(self.max_contracts, max(1, int(stopped_trade.get("count", 1))))
        dry_run = (self.mode == "PAPER") or bool(self.ai_settings.get("dryRun", False)) or (str(stopped_trade.get("mode", "")).upper() == "PAPER")
        trade_mode = "PAPER" if dry_run else "LIVE"
        try:
            order_res = kalshi_trader.place_order(
                ticker=ticker,
                side=opposite_side.lower(),
                count=count,
                limit_price_dollars=opposite_ask,
                dry_run=dry_run
            )
            if order_res.get("success"):
                fill_price = float(order_res.get("filled_price", opposite_ask))
                fill_cost = round(fill_price * count, 4)
                reversal_record = {
                    "id": f"{'sim' if trade_mode == 'PAPER' else 'live'}_{uuid.uuid4().hex[:8]}",
                    "client_order_id": order_res.get("client_order_id") or order_res.get("order_id", str(uuid.uuid4())),
                    "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                    "interval_close_time": stopped_trade.get("interval_close_time"),
                    "close_epoch": stopped_trade.get("close_epoch"),
                    "ticker": ticker,
                    "title": f"Reversal Flip to {opposite_side}",
                    "market_snapshot": {
                        "price": spot_price,
                        "target": stopped_trade.get("strike", 0.0),
                        "confidence": conf,
                        "conviction_grade": "REVERSAL FLIP",
                        "primary_edge": f"Dynamic Reversal ({stopped_side} -> {opposite_side})"
                    },
                    "strike": stopped_trade.get("strike", 0.0),
                    "direction": opposite_side,
                    "recommendation": f"REVERSAL FLIP ({opposite_side})",
                    "conviction_grade": "REVERSAL FLIP",
                    "conviction_badge": f"🔄 REVERSAL ({int(conf)}%)",
                    "probability_percent": conf,
                    "trade_source": "SCALP",
                    "trading_style": "SCALP",
                    "side": opposite_side,
                    "entry_price": fill_price,
                    "count": count,
                    "cost": fill_cost,
                    "mode": trade_mode,
                    "status": "OPEN",
                    "result": "PENDING",
                    "pnl": 0.0,
                    "catalysts": [f"Early bailout stop on {stopped_side}; momentum reversed to {opposite_side}"],
                    "is_reversal": True,
                    "reversal_of": stopped_trade.get("id"),
                    "btc_price_at_entry": spot_price
                }
                with _history_lock:
                    trades_hist = self.get_trades_history()
                    trades_hist.append(reversal_record)
                    self._save_trades_history(trades_hist)

                if trade_mode == "PAPER":
                    try:
                        from backend.btc.paper_balance import update_balance
                        update_balance(-fill_cost)
                    except Exception as ep:
                        logger.warning(f"Failed to deduct paper balance for reversal: {ep}")

                logger.info(f"[AutoExecutor] Successfully opened REVERSAL position {reversal_record['id']} ({opposite_side})")
                return reversal_record
            else:
                if order_res.get("ambiguous"):
                    logger.error(
                        f"[AutoExecutor] CRITICAL: Reversal order outcome ambiguous after timeout! "
                        f"Ticker: '{order_res.get('ticker', ticker)}', Client Order ID: '{order_res.get('client_order_id')}'. "
                        f"Error: {order_res.get('error')}. MANUAL VERIFICATION REQUIRED ON KALSHI."
                    )
                else:
                    logger.error(f"[AutoExecutor] Reversal order placement failed: {order_res.get('error')}")
        except Exception as e:
            logger.error(f"[AutoExecutor] Exception executing reversal order: {e}", exc_info=True)

        return None

    def _attempt_profit_reentry(
        self,
        closed_trade: Dict[str, Any],
        minutes_remaining: float,
        spot_price: float
    ) -> Optional[Dict[str, Any]]:
        """
        After securing a take-profit or trailing take-profit, evaluate if there is still
        enough time (>= 4.0 minutes) and conviction to enter a fresh contract in the same
        or newly confirmed trend direction.
        """
        if minutes_remaining < 4.0:
            logger.info(f"[AutoExecutor] Profit re-entry skipped: Only {minutes_remaining:.1f}m remaining in interval (< 4.0m minimum).")
            return None

        ticker = closed_trade.get("ticker", "")
        # Prevent spamming multiple re-entries in the exact same interval (max 1 re-entry per contract)
        interval_trades = self.get_trades_history()
        already_reentered = any(
            t.get("ticker") == ticker and t.get("is_profit_reentry")
            for t in interval_trades
        )
        if already_reentered:
            logger.info(f"[AutoExecutor] Profit re-entry skipped: Interval {ticker} already executed a profit re-entry.")
            return None

        # Fetch active market and live analysis
        try:
            from backend.engine.multi_asset_fetcher import is_market_open, fetch_asset_candles as fetch_candles
            from backend.btc.indicators import add_all_indicators
            from backend.btc.analyzer import evaluate_next_15m_contract
            from backend.btc.kalshi_trader import kalshi_trader

            active_m = kalshi_trader.get_active_15m_market(series_ticker=f"KX{self.asset}15M", allow_synthetic=(self.mode == "PAPER"), min_seconds_left=120)
            if not active_m:
                logger.info("[AutoExecutor] Profit re-entry skipped: No active Kalshi contract found with >=120s remaining.")
                return None

            strike = float(active_m.get("strike_price") or closed_trade.get("strike", 0.0))
            df_c = fetch_candles(self.asset, timeframe="15m", limit=60)
            if df_c is None or df_c.empty:
                return None

            df_ind = add_all_indicators(df_c)
            forecast = evaluate_next_15m_contract(df_ind, target_price=strike, kalshi_m=active_m, trading_style=self.ai_settings.get("tradingStyle", "MOMENTUM_SURFER"), asset=self.asset)

            pred_dir = str(forecast.get("direction", "")).upper()
            if pred_dir == "PASS" or "PASS" in str(forecast.get("recommendation", "")):
                # If Force Trade is enabled, check underlying pre-gate direction
                if bool(self.ai_settings.get("ignorePass", False)):
                    pre_dir = str(forecast.get("pre_gate_direction", "")).upper()
                    if pre_dir in ["ABOVE", "YES", "UP"]:
                        direction = "ABOVE"
                        side = "yes"
                    elif pre_dir in ["BELOW", "NO", "DOWN"]:
                        direction = "BELOW"
                        side = "no"
                    else:
                        logger.info("[AutoExecutor] Profit re-entry: Setup is PASS even with Force Trade. Standing down.")
                        return None
                else:
                    logger.info("[AutoExecutor] Profit re-entry: Fresh evaluation returned PASS. Preserving profits.")
                    return None
            elif pred_dir in ["ABOVE", "YES", "UP"]:
                direction = "ABOVE"
                side = "yes"
            else:
                direction = "BELOW"
                side = "no"

            closed_side = str(closed_trade.get("side", "")).lower()
            if side != closed_side:
                logger.info(f"[AutoExecutor] Profit re-entry skipped: Model suggested {side.upper()} but original trade was {closed_side.upper()}. Only trend-aligned re-entries are permitted.")
                return None

            conf = float(forecast.get("probability_percent", 50.0))
            min_conf = float(self.ai_settings.get("minConf", 60.0))
            if conf < min_conf and not bool(self.ai_settings.get("ignorePass", False)):
                logger.info(f"[AutoExecutor] Profit re-entry: Model confidence {conf:.1f}% below minimum {min_conf}%. Standing down.")
                return None

            # Check market price on chosen side
            market_price = float(active_m.get(f"{side}_ask", 0.50) or 0.50)
            max_reentry_ask = float(self.ai_settings.get("profitReentryMaxAsk", 0.75))
            if market_price >= max_reentry_ask:
                logger.info(f"[AutoExecutor] Profit re-entry: {side.upper()} ask is ${market_price:.2f} >= ${max_reentry_ask:.2f} (too expensive/poor risk-reward). Standing down.")
                return None

            # Calculate contract count
            max_cap = float(self.ai_settings.get("maxCap", 0.0))
            unit_price_est = min(0.99, max(0.01, market_price + 0.04))
            if max_cap > 0:
                contracts_to_buy = max(1, int(max_cap // unit_price_est))
            else:
                contracts_to_buy = self.max_contracts

            dry_run = (self.mode == "PAPER") or bool(self.ai_settings.get("dryRun", False))
            trade_mode = "PAPER" if dry_run else "LIVE"

            logger.info(
                f"[AutoExecutor] EXECUTING POST-TAKE-PROFIT RE-ENTRY: Buying {side.upper()} on {ticker} "
                f"@ ${market_price:.2f} ({minutes_remaining:.1f}m left, Conf: {conf:.1f}%, Count: {contracts_to_buy})"
            )

            order_res = kalshi_trader.place_order(
                ticker=ticker,
                side=side,
                count=contracts_to_buy,
                limit_price_dollars=market_price,
                dry_run=dry_run,
                slippage_buffer_dollars=0.04
            )

            if order_res.get("success"):
                fill_price = float(order_res.get("filled_price", market_price))
                fill_cost = round(fill_price * contracts_to_buy, 4)
                reentry_record = {
                    "id": f"{'sim' if trade_mode == 'PAPER' else 'live'}_{uuid.uuid4().hex[:8]}",
                    "client_order_id": order_res.get("client_order_id") or order_res.get("order_id", str(uuid.uuid4())),
                    "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                    "interval_close_time": active_m.get("close_time", closed_trade.get("interval_close_time")),
                    "close_epoch": closed_trade.get("close_epoch"),
                    "ticker": ticker,
                    "title": f"Profit Re-Entry ({side.upper()})",
                    "market_snapshot": {
                        "price": spot_price,
                        "target": strike,
                        "confidence": conf,
                        "conviction_grade": "PROFIT RE-ENTRY",
                        "primary_edge": "Secured TP -> Fresh Trend Re-Entry",
                        "raw_features": forecast.get("raw_features", {})
                    },
                    "strike": strike,
                    "direction": direction,
                    "recommendation": f"PROFIT RE-ENTRY ({direction})",
                    "conviction_grade": "GRADE A (PROFIT RE-ENTRY)",
                    "conviction_badge": f"🎯 RE-ENTRY ({int(conf)}%)",
                    "probability_percent": conf,
                    "trade_source": "AUTO (RE-ENTRY)",
                    "trading_style": self.ai_settings.get("tradingStyle", "MOMENTUM_SURFER"),
                    "side": side.upper(),
                    "entry_price": fill_price,
                    "count": contracts_to_buy,
                    "cost": fill_cost,
                    "mode": trade_mode,
                    "status": "OPEN",
                    "result": "PENDING",
                    "pnl": 0.0,
                    "catalysts": [f"Secured take-profit; trend confirmed fresh {side.upper()} continuation with {minutes_remaining:.1f}m left"],
                    "is_profit_reentry": True,
                    "reentry_after": closed_trade.get("id"),
                    "btc_price_at_entry": spot_price
                }

                with _history_lock:
                    trades_hist = self.get_trades_history()
                    trades_hist.append(reentry_record)
                    self._save_trades_history(trades_hist)

                if trade_mode == "PAPER":
                    try:
                        from backend.btc.paper_balance import update_balance
                        update_balance(-fill_cost)
                    except Exception as ep:
                        logger.warning(f"Failed to deduct paper balance for re-entry: {ep}")

                logger.info(f"[AutoExecutor] Successfully executed PROFIT RE-ENTRY {reentry_record['id']} ({side.upper()})")
                return reentry_record
            else:
                logger.error(f"[AutoExecutor] Profit re-entry order placement failed: {order_res.get('error')}")
        except Exception as err:
            logger.error(f"[AutoExecutor] Error during profit re-entry evaluation: {err}", exc_info=True)

        return None


# Global singleton instance
_executors = {}
def get_auto_executor(asset: str = "BTC") -> AutoExecutor:
    if asset not in _executors:
        _executors[asset] = AutoExecutor(asset)
    return _executors[asset]
