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
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.btc.kalshi_trader import kalshi_trader
from backend.btc.data_fetcher import fetch_candles, get_candle_countdown
from backend.btc.indicators import add_all_indicators
from backend.btc.analyzer import evaluate_next_15m_contract

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
HISTORY_FILE = os.path.join(DATA_DIR, "trades_history.json")
CONFIG_FILE = os.path.join(DATA_DIR, "trading_config.json")

import threading
# Exit helpers load and save history while retaining the surrounding lock.
# Re-entrant locking prevents those safe nested calls from deadlocking.
_history_lock = threading.RLock()

import tempfile

def _atomic_json_write(filepath: str, data, indent: int = 2):
    """AUDIT FIX #2: Atomic JSON write — write to temp file then os.replace(), with fallback for Windows locking."""
    dir_name = os.path.dirname(filepath)
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent)
        try:
            os.replace(tmp_path, filepath)
        except PermissionError:
            # On Windows, antivirus or open file handles can briefly block replace
            time.sleep(0.05)
            try:
                os.replace(tmp_path, filepath)
            except Exception:
                with open(filepath, "w", encoding="utf-8") as fallback_f:
                    json.dump(data, fallback_f, indent=indent)
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
    except Exception:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        raise

def normalize_prediction_direction(value: Any) -> str:
    """Map analyzer and recommendation labels to the two Kalshi outcomes."""
    label = str(value or "").upper().strip()
    if not label or "PASS" in label or "CHOP" in label:
        return "PASS"
    if label in {"YES", "ABOVE", "UP"} or "BID YES" in label or "ABOVE" in label:
        return "ABOVE"
    if label in {"NO", "BELOW", "DOWN"} or "BID NO" in label or "BELOW" in label:
        return "BELOW"
    return "PASS"


class AutoExecutor:
    def __init__(self):
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
        # Instance-level trade cache (not class-level, to avoid cross-instance contamination)
        self._cached_trades: List[Dict[str, Any]] = []
        self._cached_trades_mtime: float = 0.0

        os.makedirs(DATA_DIR, exist_ok=True)
        self._load_config()

    def set_ai_settings(self, data: dict):
        self.ai_settings = data
        self._save_config()
        return {"status": "ok"}

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.enabled = bool(cfg.get("enabled", False))
                    self.mode = cfg.get("mode", "PAPER")
                    self.min_conviction = cfg.get("min_conviction", "GRADE B SETUP")
                    self.max_contracts = int(cfg.get("max_contracts", 1))
                    self.prediction_mode = bool(cfg.get("prediction_mode", True))
                    self.max_daily_risk = float(cfg.get("max_daily_risk", 25.0))
                    self.max_daily_trades = int(cfg.get("max_daily_trades", 10))
                    self.ai_settings = cfg.get("ai_settings", {})
            except Exception as e:
                logger.error(f"[AutoExecutor] Error loading config: {e}")

    def _save_config(self):
        try:
            _atomic_json_write(CONFIG_FILE, {
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
        if os.path.exists(HISTORY_FILE):
            try:
                mtime = os.path.getmtime(HISTORY_FILE)
                with _history_lock:
                    if self._cached_trades and self._cached_trades_mtime == mtime:
                        return list(self._cached_trades)
                    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                        trades = json.load(f)
                        self._cached_trades = trades
                        self._cached_trades_mtime = mtime
                        return list(trades)
            except Exception:
                return list(self._cached_trades) if self._cached_trades else []
        return []

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        trades = self.get_trades_history()
        return trades[-limit:][::-1] if limit else trades[::-1]

    def _save_trades_history(self, trades: List[Dict[str, Any]]):
        try:
            with _history_lock:
                _atomic_json_write(HISTORY_FILE, trades)
                self._cached_trades = trades
                self._cached_trades_mtime = os.path.getmtime(HISTORY_FILE)
        except Exception as e:
            logger.error(f"[AutoExecutor] Error saving trades: {e}")

    def set_enabled(self, enabled: bool) -> Dict[str, Any]:
        self.enabled = enabled
        self._save_config()
        return {"status": "ok", "enabled": self.enabled, "mode": self.mode}

    def set_mode(self, mode: str) -> Dict[str, Any]:
        mode_clean = mode.upper().strip()
        if mode_clean in ["PAPER", "LIVE"]:
            self.mode = mode_clean
            self._save_config()
            return {"status": "ok", "mode": self.mode}
        return {"status": "error", "message": f"Invalid mode {mode}. Choose PAPER or LIVE."}

    def set_conviction_threshold(self, threshold: str) -> Dict[str, Any]:
        clean = threshold.upper().strip()
        if "A+" in clean:
            self.min_conviction = "GRADE A+ SETUP"
        elif "B" in clean:
            self.min_conviction = "GRADE B SETUP"
        else:
            self.min_conviction = "GRADE A SETUP"
        self._save_config()
        return {"status": "ok", "min_conviction": self.min_conviction}

    def set_max_contracts(self, count: int) -> Dict[str, Any]:
        c = max(1, min(int(count), 9999))
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
        total_pnl = sum(float(t.get("pnl", 0.0)) for t in mode_trades)
        win_rate = round((wins / max(1, wins + losses)) * 100.0, 1) if (wins + losses) > 0 else 0.0

        # Calculate daily ET statistics
        from zoneinfo import ZoneInfo
        today_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
        today_trades = [
            t for t in mode_trades
            if str(t.get("timestamp", "")).startswith(today_str)
        ]
        today_trade_count = len(today_trades)
        today_realized_pnl = sum(float(t.get("pnl", 0.0)) for t in today_trades)

        active_market = kalshi_trader.get_active_15m_market()

        # Compute live unrealized (mark-to-market) P&L for each open trade
        open_pnl_dollars = 0.0
        if active_market and open_trades:
            am_yes_bid = float(active_market.get("yes_bid") or 0.0)
            am_no_bid  = float(active_market.get("no_bid")  or 0.0)
            for t in open_trades:
                side = str(t.get("side", "YES")).upper()
                entry = float(t.get("entry_price", 0.5))
                count = int(t.get("count", 1))
                current_bid = am_yes_bid if side == "YES" else am_no_bid
                live_pnl = round((current_bid - entry) * count, 4) if current_bid > 0 else 0.0
                t["live_pnl"] = live_pnl          # annotate trade dict for UI
                t["current_bid"] = current_bid
                open_pnl_dollars += live_pnl

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
            elif today_realized_pnl <= -abs(self.max_daily_risk):
                is_risk_paused = True
                pause_reason = f"Daily loss limit reached (-${abs(today_realized_pnl):.2f}/-${abs(self.max_daily_risk):.2f})"

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
            "open_trades_count": len(open_trades),
            "open_trades": open_trades,
            "open_pnl_dollars": round(open_pnl_dollars, 4),   # live unrealized P&L
            "recent_trades": mode_trades[-15:][::-1],  # latest 15 trades of current mode first
            "active_market": active_market,
            "prediction_accuracy": prediction_accuracy,
        }

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

    def check_settlements(self, trades: Optional[List[Dict[str, Any]]] = None):
        """
        Settle completed Kalshi trades from Kalshi's own YES/NO result.

        A candle close is not Kalshi's settlement authority, so it is only kept
        as a legacy fallback for non-Kalshi records that have a valid strike.
        """
        with _history_lock:
            if trades is None:
                if os.path.exists(HISTORY_FILE):
                    try:
                        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                            trades = json.load(f)
                    except Exception:
                        trades = []
                else:
                    trades = []

            modified = False
            now_ts = time.time()
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
                        t["prediction_correct"] = is_win if t.get("prediction_kind") == "AUTO" else None
                        if not is_win:
                            try:
                                from backend.btc.loss_analyzer import loss_analyzer
                                t["loss_analysis"] = loss_analyzer.diagnose_loss(t)
                            except Exception as ele:
                                logger.warning(f"[AutoExecutor] Loss diagnosis error: {ele}")
                        if settle_price is not None and settle_price > 0:
                            t["settle_price"] = settle_price
                        t["pnl"] = round(((1.0 - entry_price) * count) if is_win else (-entry_price * count), 4)
                        t["settled_at"] = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET")
                        modified = True

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
                            settle_candles_df = fetch_candles(timeframe="15m", limit=5)
                        except Exception:
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
                except Exception as e:
                    logger.error(f"[AutoExecutor] Error checking settlement for trade {t.get('id')}: {e}")

            if modified:
                try:
                    _atomic_json_write(HISTORY_FILE, trades)
                    # Trigger background retrain on singleton MLEngine
                    try:
                        from backend.btc.ml_engine import get_ml_engine
                        get_ml_engine().train()
                    except Exception:
                        pass
                except Exception as e:
                    logger.error(f"[AutoExecutor] Error saving trades in check_settlements: {e}")

    def check_and_execute_rollover(self) -> Optional[Dict[str, Any]]:
        """
        Core autonomous trigger:
        Evaluates at rollover (first 60 seconds of a new 15-minute contract interval).
        """
        now = time.time()
        if (now - self.last_check_time) < 4.0:
            return None
        self.last_check_time = now

        countdown_info = get_candle_countdown(timeframe="15m")
        sec_left = countdown_info.get("seconds_left", 900)
        sec_elapsed = 900 - sec_left

        # The standard rollover evaluation window is the first 60 seconds
        is_rollover_window = sec_elapsed <= 60 or sec_left >= 840
        # The prediction mode window is 30-55 seconds elapsed to avoid missing the narrow 5s window
        is_prediction_window = 30 <= sec_elapsed <= 55 or 845 <= sec_left <= 870

        window_valid = is_prediction_window if self.prediction_mode else is_rollover_window
        if not window_valid and not (sec_left <= 10):
            return None

        # Fetch active Kalshi KXBTC15M market
        active_m = kalshi_trader.get_active_15m_market(allow_synthetic=(self.mode == "PAPER"))
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

        # A prediction without the contract's official target must never create
        # an order; a zero target previously made NO trades settle incorrectly.
        try:
            strike = float(active_m.get("strike_price") or 0.0)
        except (TypeError, ValueError):
            strike = 0.0
        if strike <= 0:
            logger.error("[AutoExecutor] Active Kalshi market has no valid floor strike; skipping %s", current_interval_id)
            return None

        # Fetch technical indicator data
        df = fetch_candles(timeframe="15m", limit=1000)
        df_ind = add_all_indicators(df)

        # Inject historical market intervals directly into the ML Engine to train it instantly
        # rather than waiting for it to slowly accumulate actual paper trades.
        try:
            from backend.btc.ml_engine import get_ml_engine
            import os
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
            ml_engine = get_ml_engine(data_dir)
            if not ml_engine.is_trained:
                ml_engine.self_train_on_historical_market(df_ind)
        except Exception as e:
            logger.error(f"[AutoExecutor] Failed to self-train ML Engine: {e}")

        forecast = evaluate_next_15m_contract(df_ind, target_price=strike)

        raw_score = float(forecast.get("probability_percent", 50.0))
        edge_label = str(forecast.get("primary_edge", ""))
        rec = forecast.get("recommendation", "")
        grade = forecast.get("conviction_grade", "")
        direction = normalize_prediction_direction(forecast.get("direction") or rec)

        ignore_pass = bool(self.ai_settings.get("ignorePass", False))

        # Handle PASS direction filtering or Force Trade override
        if direction == "PASS":
            if ignore_pass and raw_score > 0:
                # Force trade based on highest probable direction from probability score or ML signal
                direction = "ABOVE" if raw_score >= 50.0 else "BELOW"
                logger.info(f"[AutoExecutor] 'Force Trade on PASS' enabled. Overriding PASS direction to {direction} (Score: {raw_score}%)")
            else:
                logger.debug("[AutoExecutor] Skipping because direction is PASS")
                return None

        # Strict Filter 2: Conviction & Settings Thresholds
        meets_conviction = False
        
        # ML settings overrides
        min_conf = float(self.ai_settings.get("minConf", 0.0))
        edge_multiplier = float(self.ai_settings.get("edgeWeightFactor", 1.0)) if self.ai_settings.get("edgeWeightOn") else 1.0
        
        actual_conf = raw_score
        if "High Confluence" in edge_label:
            actual_conf = min(99.0, raw_score * edge_multiplier)

        # Base threshold check against minConf
        if min_conf > 0:
            if actual_conf >= min_conf:
                meets_conviction = True
        else:
            # Fallback to grade logic
            if self.prediction_mode:
                meets_conviction = True
            else:
                if self.min_conviction == "GRADE A+ SETUP" and "A+" in grade:
                    meets_conviction = True
                elif self.min_conviction == "GRADE A SETUP" and ("A+" in grade or "GRADE A " in grade or "ML" in grade):
                    meets_conviction = True
                elif self.min_conviction == "GRADE B SETUP" and ("A+" in grade or "GRADE A " in grade or "B SETUP" in grade or "ML" in grade):
                    meets_conviction = True

        if not meets_conviction:
            logger.debug(f"[AutoExecutor] Skipping because conviction not met: {actual_conf} < {min_conf} (Grade: {grade})")
            return None

        # If bot is disabled, do not execute
        if not self.enabled:
            logger.debug("[AutoExecutor] Skipping because bot is disabled")
            return None

        # Strict Filter 3: Enforce Max Daily Trades & Max Daily Risk
        from zoneinfo import ZoneInfo
        today_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
        today_trades = [
            t for t in trades
            if t.get("mode", self.mode).upper() == self.mode
            and str(t.get("timestamp", "")).startswith(today_str)
        ]
        if len(today_trades) >= self.max_daily_trades:
            logger.info(f"[AutoExecutor] Max daily trades reached ({len(today_trades)}/{self.max_daily_trades}). Skipping auto execution.")
            return None

        today_net_pnl = sum(float(t.get("pnl", 0.0)) for t in today_trades if t.get("status") in ["SETTLED", "CLOSED"])
        # AUDIT FIX #1: Also account for open floating risk (collateral at risk from unsettled trades)
        open_collateral = sum(
            float(t.get("entry_price", 0.50)) * int(t.get("count", 1))
            for t in today_trades
            if t.get("status") in ["OPEN", "PENDING"]
        )
        effective_risk = today_net_pnl - open_collateral
        if effective_risk <= -abs(self.max_daily_risk):
            logger.info(f"[AutoExecutor] Max daily risk limit reached (Settled PnL: ${today_net_pnl:.2f}, Open Collateral: ${open_collateral:.2f}, Effective: ${effective_risk:.2f} <= -${self.max_daily_risk:.2f}). Skipping auto execution.")
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
        ABSOLUTE_MAX_CONTRACTS = 50

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
            
        # 3. Execution Delay
        exec_delay = int(self.ai_settings.get("execDelay", 0))
        if exec_delay > 0:
            logger.info(f"[AutoExecutor] Delaying execution by {exec_delay}s...")
            time.sleep(exec_delay)
            
        if self.mode == "LIVE":

            bal_res = kalshi_trader.get_balance()
            if bal_res.get("success", False):
                avail_bal = float(bal_res.get("balance_dollars", 0.0))
                unit_price = min(0.99, max(0.01, float(market_price) + 0.04))
                if unit_price > 0 and avail_bal < (unit_price * contracts_to_buy):
                    affordable = int(avail_bal // unit_price)
                    if affordable >= 1:
                        contracts_to_buy = affordable

        # Execute Order (Paper or Live)
        order_res = kalshi_trader.place_order(
            ticker=current_interval_id,
            side=side,
            count=contracts_to_buy,
            limit_price_dollars=market_price,
            dry_run=dry_run
        )

        if order_res.get("success", False):
            if self.mode == "PAPER":
                try:
                    from backend.btc.paper_balance import update_balance
                    cost = float(order_res.get("cost", market_price * contracts_to_buy))
                    update_balance(-cost)
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
                "prediction_direction": direction,
                "prediction_generated_at": prediction_generated_at,
                "accuracy_eligible": True,
                "interval_close_time": close_time_str,
                "close_epoch": close_epoch,
                "ticker": current_interval_id,
                "title": active_m.get("title", ""),
                "market_snapshot": {
                    "price": df_ind.iloc[-1]["close"],
                    "target": strike,
                    "confidence": forecast.get("probability_percent"),
                    "conviction_grade": forecast.get("conviction_grade"),
                    "primary_edge": forecast.get("primary_edge"),
                    "raw_features": forecast.get("raw_features", {})
                },
                "strike": strike,
                "direction": direction,
                "recommendation": rec,
                "conviction_grade": grade,
                "conviction_badge": forecast.get("conviction_badge", ""),
                "probability_percent": forecast.get("probability_percent", 50),
                "side": side.upper(),
                "entry_price": market_price,
                "count": contracts_to_buy,
                "cost": round(market_price * contracts_to_buy, 4),
                "mode": self.mode,
                "status": "OPEN",
                "result": "PENDING",
                "pnl": 0.0,
                "catalysts": forecast.get("catalysts", [])
            }

            trades.append(trade_record)
            self._save_trades_history(trades)

            # Connect with scalp_engine for early profit exits if scalping is enabled
            try:
                from backend.btc.scalp_engine import scalp_engine
                if getattr(scalp_engine, "enabled", False):
                    scalp_engine.register_position(trade_record)
            except Exception as se_err:
                logger.warning(f"[AutoExecutor] Could not register trade with ScalpEngine: {se_err}")

            return trade_record
        else:
            logger.error(f"[AutoExecutor] Order failed: {order_res.get('error')}")

        return None

    def execute_manual_trade(self, direction: str) -> Dict[str, Any]:
        """
        Enables user to click 1-click execution for the current interval directly from the UI.
        """
        active_m = kalshi_trader.get_active_15m_market(allow_synthetic=(self.mode == "PAPER"))
        if not active_m:
            return {"success": False, "error": "No active KXBTC15M market found."}

        side = "yes" if direction.upper() == "ABOVE" else "no"
        market_price = active_m.get("yes_ask" if side == "yes" else "no_ask") or 0.50

        # Determine affordable contract count for live or paper
        
        # ML Settings Overrides: Use maxCap to size position
        max_cap = float(self.ai_settings.get("maxCap", 0.0))
        unit_price_est = min(0.99, max(0.01, float(market_price) + 0.04))
        
        if max_cap > 0:
            contracts_to_buy = int(max_cap // unit_price_est)
            if contracts_to_buy < 1:
                contracts_to_buy = 1
        else:
            contracts_to_buy = self.max_contracts

        # 2. Dry Run
        dry_run = (self.mode == "PAPER")
        if self.ai_settings.get("dryRun", False):
            dry_run = True
            
        # 3. Execution Delay
        exec_delay = int(self.ai_settings.get("execDelay", 0))
        if exec_delay > 0:
            logger.info(f"[AutoExecutor] Delaying execution by {exec_delay}s...")
            time.sleep(exec_delay)
            
        if self.mode == "LIVE":

            bal_res = kalshi_trader.get_balance()
            if bal_res.get("success", False):
                avail_bal = float(bal_res.get("balance_dollars", 0.0))
                unit_price = min(0.99, max(0.01, float(market_price) + 0.04))
                if unit_price > 0 and avail_bal < (unit_price * contracts_to_buy):
                    affordable = int(avail_bal // unit_price)
                    if affordable >= 1:
                        contracts_to_buy = affordable

        order_res = kalshi_trader.place_order(
            ticker=active_m.get("ticker", ""),
            side=side,
            count=contracts_to_buy,
            limit_price_dollars=market_price,
            dry_run=dry_run
        )

        if order_res.get("success", False):
            if self.mode == "PAPER":
                try:
                    from backend.btc.paper_balance import update_balance
                    cost = float(order_res.get("cost", market_price * contracts_to_buy))
                    update_balance(-cost)
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
                from backend.btc.data_fetcher import get_live_15m_target_data, get_btc_ticker
                target_data = get_live_15m_target_data()
                strike_val = target_data.get("target_price") or get_btc_ticker().get("price", 78000.0)

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
                "side": side.upper(),
                "entry_price": market_price,
                "count": contracts_to_buy,
                "cost": round(market_price * contracts_to_buy, 4),
                "mode": self.mode,
                "status": "OPEN",
                "result": "PENDING",
                "pnl": 0.0,
                "catalysts": ["Manual trader button trigger"]
            }
            trades.append(trade_record)
            self._save_trades_history(trades)

            # Connect with scalp_engine for early profit exits if scalping is enabled
            try:
                from backend.btc.scalp_engine import scalp_engine
                if getattr(scalp_engine, "enabled", False):
                    scalp_engine.register_position(trade_record)
            except Exception as se_err:
                logger.warning(f"[AutoExecutor] Could not register manual trade with ScalpEngine: {se_err}")

            return {"success": True, "trade": trade_record}

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
        exit_res = kalshi_trader.close_position(
            ticker=ticker,
            purchased_side=side,
            count=count,
            dry_run=(mode == "PAPER"),
            estimated_exit_price=estimated_exit_price,
        )
        if not exit_res.get("success"):
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
                        from backend.btc.data_fetcher import get_btc_ticker
                        spot = float(get_btc_ticker().get("price", 0.0))
                        if spot > 0:
                            diff = (spot - strike) if side == "YES" else (strike - spot)
                            import math
                            prob = 1.0 / (1.0 + math.exp(-diff / 150.0))
                            est_exit = round(max(0.10, min(0.90, prob)), 4)
                    except Exception:
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


# Global singleton instance
auto_executor = AutoExecutor()
