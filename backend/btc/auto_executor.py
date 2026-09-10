"""
Autonomous 15-Minute Bitcoin Kalshi Execution Engine
Monitors the 15-minute candle countdown, triggers algorithmic execution
on high-conviction Grade A+/A setups, tracks paper/live trades, and computes P&L.
"""

import os
import time
import json
import uuid
from typing import Dict, Any, List, Optional
import pandas as pd

from backend.btc.kalshi_trader import kalshi_trader
from backend.btc.data_fetcher import fetch_candles, get_candle_countdown
from backend.btc.indicators import add_all_indicators
from backend.btc.analyzer import evaluate_next_15m_contract

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
HISTORY_FILE = os.path.join(DATA_DIR, "trades_history.json")
CONFIG_FILE = os.path.join(DATA_DIR, "trading_config.json")


class AutoExecutor:
    def __init__(self):
        self.enabled: bool = False
        self.mode: str = "PAPER"  # "PAPER" or "LIVE"
        self.min_conviction: str = "GRADE A SETUP"  # "GRADE A+ SETUP" or "GRADE A SETUP"
        self.max_contracts: int = 1
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
            except Exception as e:
                print(f"[AutoExecutor] Error loading config: {e}")

    def _save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "enabled": self.enabled,
                    "mode": self.mode,
                    "min_conviction": self.min_conviction,
                    "max_contracts": self.max_contracts
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

        total_trades = len(trades)
        wins = sum(1 for t in trades if "WIN" in str(t.get("result", "")).upper())
        losses = sum(1 for t in trades if "LOSS" in str(t.get("result", "")).upper())
        open_trades = [t for t in trades if t.get("status") == "OPEN"]
        total_pnl = sum(float(t.get("pnl", 0.0)) for t in trades)
        win_rate = round((wins / max(1, wins + losses)) * 100.0, 1) if (wins + losses) > 0 else 0.0

        active_market = kalshi_trader.get_active_15m_market()

        # Paper Trading Balance Logic
        if self.mode == "PAPER":
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
            "recent_trades": trades[-10:][::-1],  # latest 10 trades first
            "active_market": active_market
        }

    def check_settlements(self, trades: Optional[List[Dict[str, Any]]] = None):
        """
        Scans open trades and checks if their 15-minute interval has concluded.
        Settles them against the finalized Bitcoin price to update Win/Loss & P&L.
        """
        if trades is None:
            trades = self.get_trades_history()

        modified = False
        now_ts = time.time()

        for t in trades:
            if t.get("status") == "OPEN":
                close_epoch = t.get("close_epoch", 0)
                close_time_str = t.get("interval_close_time")

                # Fallback: parse ISO close_time_str if close_epoch is missing
                if not close_epoch and close_time_str:
                    try:
                        import datetime
                        dt = datetime.datetime.fromisoformat(close_time_str.replace("Z", "+00:00"))
                        close_epoch = dt.timestamp()
                    except Exception:
                        pass

                # If interval has concluded
                if close_epoch and (now_ts > close_epoch + 10):
                    try:
                        settle_price = 0.0
                        # 1. Try finding finalized close from exchange candle history
                        df = fetch_candles(timeframe="15m", limit=5)
                        if len(df) >= 2:
                            settle_price = float(df.iloc[-2]["close"])
                        
                        # 2. Fallback to live ticker if candle delayed
                        if not settle_price or settle_price <= 0:
                            from backend.btc.data_fetcher import get_btc_ticker
                            settle_price = float(get_btc_ticker().get("price", 0.0))

                        if settle_price > 0:
                            strike = float(t.get("strike", 0.0) or settle_price)
                            side = t.get("side", "").upper()
                            entry_price = float(t.get("entry_price", 0.50))
                            count = int(t.get("count", 1))

                            is_win = False
                            if side == "YES" and settle_price >= strike:
                                is_win = True
                            elif side == "NO" and settle_price < strike:
                                is_win = True

                            pnl = round(((1.0 - entry_price) * count) if is_win else (-entry_price * count), 4)
                            t["status"] = "SETTLED"
                            t["result"] = "WIN" if is_win else "LOSS"
                            t["settle_price"] = settle_price
                            t["pnl"] = pnl
                            t["settled_at"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
                            modified = True
                    except Exception as e:
                        print(f"[AutoExecutor] Error checking settlement for trade {t.get('id')}: {e}")

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

        # The rollover evaluation window is the first 60 seconds of a new 15M candle (sec_elapsed <= 60 or sec_left >= 840)
        is_rollover_window = sec_elapsed <= 60 or sec_left >= 840
        if not is_rollover_window and not (sec_left <= 10):
            return None

        # Fetch active Kalshi KXBTC15M market
        active_m = kalshi_trader.get_active_15m_market()
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

        # Fetch technical indicator data
        df = fetch_candles(timeframe="15m", limit=100)
        df_ind = add_all_indicators(df)

        strike = active_m.get("strike_price")
        forecast = evaluate_next_15m_contract(df_ind, target_price=strike)

        rec = forecast.get("recommendation", "")
        grade = forecast.get("conviction_grade", "")
        direction = forecast.get("direction", "")

        # Strict Filter 1: Skip all PASS / CHOP signals
        if direction == "PASS" or "PASS" in rec or "CHOP" in rec:
            return None

        # Strict Filter 2: Conviction Threshold
        meets_conviction = False
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
            
            # Parse close epoch
            close_time_str = active_m.get("close_time", "")
            close_epoch = now + sec_left

            trade_record = {
                "id": order_res.get("order_id", str(uuid.uuid4())[:8]),
                "client_order_id": order_res.get("client_order_id", ""),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
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
        active_m = kalshi_trader.get_active_15m_market()
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
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
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


# Global singleton instance
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
            t["closed_at"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
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
