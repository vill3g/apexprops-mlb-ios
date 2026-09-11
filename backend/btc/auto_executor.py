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
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.btc.kalshi_trader import kalshi_trader
from backend.btc.data_fetcher import fetch_candles, get_candle_countdown
from backend.btc.indicators import add_all_indicators
from backend.btc.analyzer import evaluate_next_15m_contract

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
HISTORY_FILE = os.path.join(DATA_DIR, "trades_history.json")
CONFIG_FILE = os.path.join(DATA_DIR, "trading_config.json")


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
        self.min_conviction: str = "GRADE A SETUP"  # "GRADE A+ SETUP" or "GRADE A SETUP"
        self.max_contracts: int = 1
        self.prediction_mode: bool = False
        self.last_traded_interval: Optional[str] = None
        self.last_check_time: float = 0.0

        os.makedirs(DATA_DIR, exist_ok=True)
        self._load_config()

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.enabled = bool(cfg.get("enabled", False))
                    self.mode = cfg.get("mode", "PAPER")
                    self.min_conviction = cfg.get("min_conviction", "GRADE A SETUP")
                    self.max_contracts = int(cfg.get("max_contracts", 1))
                    self.prediction_mode = bool(cfg.get("prediction_mode", False))
            except Exception as e:
                print(f"[AutoExecutor] Error loading config: {e}")

    def _save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "enabled": self.enabled,
                    "mode": self.mode,
                    "min_conviction": self.min_conviction,
                    "max_contracts": self.max_contracts,
                    "prediction_mode": self.prediction_mode
                }, f, indent=2)
        except Exception as e:
            print(f"[AutoExecutor] Error saving config: {e}")

    def get_trades_history(self) -> List[Dict[str, Any]]:
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_trades_history(self, trades: List[Dict[str, Any]]):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(trades, f, indent=2)
        except Exception as e:
            print(f"[AutoExecutor] Error saving trades: {e}")

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
        else:
            self.min_conviction = "GRADE A SETUP"
        self._save_config()
        return {"status": "ok", "min_conviction": self.min_conviction}

    def set_max_contracts(self, count: int) -> Dict[str, Any]:
        c = max(1, min(int(count), 20))
        self.max_contracts = c
        self._save_config()
        return {"status": "ok", "max_contracts": self.max_contracts}

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

        active_market = kalshi_trader.get_active_15m_market()

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

        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "min_conviction": self.min_conviction,
            "max_contracts": self.max_contracts,
            "prediction_mode": self.prediction_mode,
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
        """Settle completed Kalshi trades from Kalshi's official YES/NO result."""
        if trades is None:
            trades = self.get_trades_history()

        modified = False
        now_ts = time.time()
        settle_candles_df = None
        official_results: Dict[str, Dict[str, Any]] = {}

        for t in trades:
            if t.get("status") != "OPEN":
                continue
            close_epoch = t.get("close_epoch", 0)
            close_time_str = t.get("interval_close_time")
            if not close_epoch and close_time_str:
                try:
                    close_epoch = datetime.fromisoformat(close_time_str.replace("Z", "+00:00")).timestamp()
                except (TypeError, ValueError):
                    continue
            if not close_epoch or now_ts <= float(close_epoch) + 10:
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

                # A Kalshi trade waits for Kalshi's posted outcome; an exchange
                # candle must never decide whether an official contract won.
                if t.get("prediction_kind") == "AUTO" or ticker.startswith("KX"):
                    continue

                strike = float(t.get("strike", 0.0) or 0.0)
                if strike <= 0:
                    continue
                if settle_candles_df is None:
                    settle_candles_df = fetch_candles(timeframe="15m", limit=5)
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
            self._save_trades_history(trades)

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
        # The prediction mode window is exactly 1 minute after contract start (60-65 seconds elapsed)
        is_prediction_window = 60 <= sec_elapsed <= 65 or 835 <= sec_left <= 840

        window_valid = is_prediction_window if self.prediction_mode else is_rollover_window
        
        if not window_valid and not (sec_left <= 10):
            return None

        # Fetch active Kalshi KXBTC15M market
        active_m = kalshi_trader.get_active_15m_market(allow_synthetic=(self.mode == "PAPER"))
        if not active_m:
            return None

        current_interval_id = active_m.get("ticker", "")
        if not current_interval_id or current_interval_id == self.last_traded_interval:
            return None

        # Check if already traded in history
        trades = self.get_trades_history()
        if any(t.get("ticker") == current_interval_id for t in trades):
            self.last_traded_interval = current_interval_id
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
        df = fetch_candles(timeframe="15m", limit=100)
        df_ind = add_all_indicators(df)
        forecast = evaluate_next_15m_contract(df_ind, target_price=strike)

        rec = forecast.get("recommendation", "")
        grade = forecast.get("conviction_grade", "")
        direction = normalize_prediction_direction(forecast.get("direction") or rec)

        # Strict Filter 1: Skip all PASS / CHOP signals
        if direction == "PASS":
            return None

        # Strict Filter 2: Conviction Threshold (Bypassed if prediction mode is enabled)
        meets_conviction = False
        if self.prediction_mode:
            meets_conviction = True
        else:
            if self.min_conviction == "GRADE A+ SETUP" and "A+" in grade:
                meets_conviction = True
            elif self.min_conviction == "GRADE A SETUP" and ("A+" in grade or "GRADE A " in grade):
                meets_conviction = True

        if not meets_conviction:
            return None

        # If bot is disabled, do not execute
        if not self.enabled:
            return None

        # Map signal to Kalshi contract side
        # "ABOVE" -> buy YES (anticipating price >= strike)
        # "BELOW" -> buy NO (anticipating price < strike)
        side = "yes" if direction == "ABOVE" else "no"
        market_price = active_m.get("yes_ask" if side == "yes" else "no_ask") or 0.50

        # Execute Order (Paper or Live)
        order_res = kalshi_trader.place_order(
            ticker=current_interval_id,
            side=side,
            count=self.max_contracts,
            limit_price_dollars=market_price,
            dry_run=(self.mode == "PAPER")
        )

        if order_res.get("success", False):
            self.last_traded_interval = current_interval_id
            
            # The prediction record is the single source carried from analyzer
            # to order to accuracy. It deliberately has its own stable ID.
            prediction_id = str(uuid.uuid4())
            prediction_generated_at = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET")
            close_time_str = active_m.get("close_time", "")
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
                "strike": strike,
                "direction": direction,
                "recommendation": rec,
                "conviction_grade": grade,
                "conviction_badge": forecast.get("conviction_badge", ""),
                "probability_percent": forecast.get("probability_percent", 50),
                "side": side.upper(),
                "entry_price": market_price,
                "count": self.max_contracts,
                "cost": round(market_price * self.max_contracts, 4),
                "mode": self.mode,
                "status": "OPEN",
                "result": "PENDING",
                "pnl": 0.0,
                "catalysts": forecast.get("catalysts", [])
            }

            trades.append(trade_record)
            self._save_trades_history(trades)
            return trade_record
        else:
            print(f"[AutoExecutor] Order failed: {order_res.get('error')}")

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

        order_res = kalshi_trader.place_order(
            ticker=active_m.get("ticker", ""),
            side=side,
            count=self.max_contracts,
            limit_price_dollars=market_price,
            dry_run=(self.mode == "PAPER")
        )

        if order_res.get("success", False):
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
                "count": self.max_contracts,
                "cost": round(market_price * self.max_contracts, 4),
                "mode": self.mode,
                "status": "OPEN",
                "result": "PENDING",
                "pnl": 0.0,
                "catalysts": ["Manual trader button trigger"]
            }
            trades.append(trade_record)
            self._save_trades_history(trades)
            return {"success": True, "trade": trade_record}

        return order_res

    def close_specific_trade(self, trade_id: str, pnl: float) -> Dict[str, Any]:
        """Close a single trade identified by ``trade_id``.
        Used by ScalpEngine to close a trade when profit/loss thresholds are hit.
        """
        trades = self.get_trades_history()
        for t in trades:
            if t.get("id") == trade_id and t.get("status") == "OPEN":
                from backend.btc.data_fetcher import get_btc_ticker
                live_price = get_btc_ticker().get("price", 0.0)
                t["status"] = "CLOSED"
                t["result"] = "CLOSED_WIN" if pnl > 0 else ("CLOSED_LOSS" if pnl < 0 else "CLOSED_FLAT")
                t["exit_price"] = live_price
                t["pnl"] = pnl
                t["closed_at"] = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET")
                self._save_trades_history(trades)
                return {"success": True, "trade_id": trade_id, "pnl": pnl}
        return {"success": False, "error": f"Trade {trade_id} not found or not open"}

    def close_open_trades(self) -> Dict[str, Any]:
        """
        1-Click close trade feature:
        Closes out any active open trades immediately at current market / live price,
        calculating realized P&L and recording result.
        """
        trades = self.get_trades_history()
        open_trades = [t for t in trades if t.get("status") == "OPEN"]
        if not open_trades:
            return {"success": False, "error": "No open trades to close."}

        from backend.btc.data_fetcher import get_btc_ticker
        live_price = get_btc_ticker().get("price", 0.0)
        closed_count = 0
        total_realized_pnl = 0.0

        for t in open_trades:
            strike = float(t.get("strike", 0.0) or live_price)
            side = t.get("side", "YES").upper()
            entry_price = float(t.get("entry_price", 0.50))
            count = int(t.get("count", 1))

            # Determine closing value based on current live price vs strike
            if live_price and strike:
                is_winning = (side == "YES" and live_price >= strike) or (side == "NO" and live_price < strike)
                # Market estimate: 0.90 if winning, 0.10 if losing
                est_exit = 0.90 if is_winning else 0.10
            else:
                est_exit = entry_price

            pnl = round((est_exit - entry_price) * count, 4)
            t["status"] = "CLOSED"
            t["result"] = "CLOSED_WIN" if pnl > 0 else ("CLOSED_LOSS" if pnl < 0 else "CLOSED_FLAT")
            t["exit_price"] = est_exit
            t["close_price"] = live_price
            t["pnl"] = pnl
            t["closed_at"] = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET")
            closed_count += 1
            total_realized_pnl += pnl

        self._save_trades_history(trades)
        return {
            "success": True,
            "closed_count": closed_count,
            "realized_pnl": round(total_realized_pnl, 2),
            "message": f"Successfully closed {closed_count} position(s) (P&L: ${total_realized_pnl:+.2f})"
        }


# Global singleton instance
auto_executor = AutoExecutor()
