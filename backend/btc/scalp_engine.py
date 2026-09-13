import logging
logger = logging.getLogger(__name__)
import json
import os
import time
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any

from backend.btc.data_fetcher import get_btc_ticker

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "scalp_config.json")

class ScalpEngine:
    """Background scalp engine for rapid 15‑min contract trades.
    
    Trades are limited to **1 per 15‑minute interval** (default). The engine
    monitors price changes and opens a trade when the absolute percent move
    exceeds ``price_move_threshold``. Open positions are automatically closed
    when profit or loss reaches the configured target (25 %).
    """

    def __init__(self):
        self._load_config()
        self.enabled = self.config.get("enabled", False)
        self._thread = None
        self._stop_event = threading.Event()
        self._last_trade_ts = 0.0  # epoch of most recent scalp trade
        self._active_trade: Dict[str, Any] = {}
        self._active_positions: Dict[str, Dict[str, Any]] = {}
        self._trade_lock = threading.Lock()
        self._current_interval_start: int = 0
        self._interval_trade_count: int = 0
        from collections import deque
        self._price_history: deque = deque(maxlen=300)

    # ------------------------------------------------------------------
    # Config handling
    # ------------------------------------------------------------------
    def _load_config(self) -> None:
        default_config = {
            "enabled": False,
            "mode": "PAPER",
            "price_move_threshold": 0.25,
            "profit_target": 0.25,
            "loss_target": 0.25,
            "take_profit_atr": 1.5,
            "max_contracts": 1,
            "max_trades_per_interval": 1,
            "interval_seconds": 900,  # 15 minutes
            "trade_cooldown_seconds": 30,
            "rolling_window_seconds": 60,
            "minimum_conviction": "A"
        }
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            except Exception as e:
                logger.warning(f"[ScalpEngine] Failed to load config from {CONFIG_PATH}: {e}. Using defaults.")
                self.config = default_config
                self._save_config()
        else:
            self.config = default_config
            self._save_config()

    def _save_config(self) -> None:
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"[ScalpEngine] Failed to save config to {CONFIG_PATH}: {e}")

    # ------------------------------------------------------------------
    # Public control API
    # ------------------------------------------------------------------
    def start(self) -> None:
        if self.enabled:
            return
        self.enabled = True
        self.config["enabled"] = True
        self._save_config()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self.enabled:
            return
        self.enabled = False
        self.config["enabled"] = False
        self._save_config()
        self._stop_event.set()
        if self._thread:
            self._thread.join()
            self._thread = None

    # ------------------------------------------------------------------
    # Core monitoring loop
    # ------------------------------------------------------------------
    def _monitor(self) -> None:
        from collections import deque
        if not hasattr(self, "_price_history"):
            self._price_history = deque(maxlen=300)

        while not self._stop_event.is_set():
            try:
                now = time.time()
                ticker = get_btc_ticker()
                current_price = float(ticker.get("price", 0.0))
                if current_price > 0:
                    self._price_history.append((now, current_price))

                interval = int(self.config.get("interval_seconds", 900) or 900)
                curr_interval_start = (int(now) // interval) * interval

                # 3. FIX: Track and enforce max_trades_per_interval
                if curr_interval_start != self._current_interval_start:
                    self._current_interval_start = curr_interval_start
                    self._interval_trade_count = 0

                max_trades = int(self.config.get("max_trades_per_interval", 1) or 1)

                # Check if there is already an active open scalp position
                with self._trade_lock:
                    has_open_position = bool(self._active_trade and self._active_trade.get("id")) or bool(getattr(self, "_active_positions", {}))

                if not has_open_position and self._interval_trade_count < max_trades:
                    # Minimum cooldown between scalps (default 30s)
                    cooldown = float(self.config.get("trade_cooldown_seconds", 30))
                    if now - self._last_trade_ts >= cooldown:
                        # 1. FIX: Track price move relative to 15-minute interval open / strike benchmark
                        from backend.btc.data_fetcher import get_live_15m_target_data
                        target_data = get_live_15m_target_data()
                        target_price = float(target_data.get("target_price") or current_price)
                        interval_pct_change = float(target_data.get("delta_pct") or 0.0)

                        # Also calculate rolling momentum window price move (default: last 60s)
                        window_sec = float(self.config.get("rolling_window_seconds", 60))
                        rolling_pct_change = 0.0
                        for ts, p in self._price_history:
                            if now - ts >= window_sec:
                                if p > 0:
                                    rolling_pct_change = ((current_price - p) / p) * 100.0
                                break

                        threshold = float(self.config.get("price_move_threshold", 0.25) or 0.25)

                        # Trigger if interval price move OR rolling momentum crosses threshold
                        triggered = False
                        pct_change = 0.0
                        if abs(interval_pct_change) >= threshold:
                            triggered = True
                            pct_change = interval_pct_change
                        elif abs(rolling_pct_change) >= threshold:
                            triggered = True
                            pct_change = rolling_pct_change

                        if triggered:
                            # Verify high confidence with BTC analyzer
                            try:
                                from backend.main import get_cached_btc_analysis
                                _, analysis = get_cached_btc_analysis()

                                next_forecast = analysis.get("target_benchmark", {}).get("next_contract_forecast", {})
                                grade = next_forecast.get("conviction_grade", "D")
                                min_conviction = self.config.get("minimum_conviction", "A")

                                def _parse_grade_score(g: str) -> int:
                                    s = str(g or "").upper()
                                    if "A+" in s:
                                        return 4
                                    if "GRADE A" in s or s == "A":
                                        return 3
                                    if "B+" in s:
                                        return 2
                                    if "GRADE B" in s or s == "B":
                                        return 1
                                    if "GRADE C" in s or s == "C":
                                        return 0
                                    return -1

                                current_grade_val = _parse_grade_score(grade)
                                min_grade_val = _parse_grade_score(min_conviction)

                                if current_grade_val >= min_grade_val:
                                    analyzer_dir = next_forecast.get("direction", "PASS")
                                    side = "yes" if pct_change > 0 else "no"

                                    if (side == "yes" and analyzer_dir == "ABOVE") or (side == "no" and analyzer_dir == "BELOW"):
                                        logger.info(
                                            f"[ScalpEngine] Triggering trade #{self._interval_trade_count + 1}/{max_trades} "
                                            f"for interval {curr_interval_start}: move {pct_change:+.3f}% (threshold: {threshold:.3f}%), "
                                            f"analyzer {analyzer_dir} ({grade})"
                                        )
                                        self._execute_trade(side, current_price)
                                        self._last_trade_ts = now
                                        self._interval_trade_count += 1
                                    else:
                                        logger.info(f"[ScalpEngine] Blocked: Scalp direction '{side}' opposes analyzer '{analyzer_dir}'")
                                else:
                                    logger.info(f"[ScalpEngine] Blocked: Conviction {grade} < min {min_conviction}")
                            except Exception as e:
                                logger.info(f"[ScalpEngine] Analyzer check failed: {e}")
            except Exception as e:
                logger.error(f"[ScalpEngine] Monitoring error: {e}")
            time.sleep(1)
        self._active_trade.clear()

    # ------------------------------------------------------------------
    # Trade execution & closure handling
    # ------------------------------------------------------------------
    def _execute_trade(self, side: str, market_price: float) -> None:
        from backend.btc.kalshi_trader import kalshi_trader
        from backend.btc.auto_executor import auto_executor
        mode = self.config.get("mode", auto_executor.mode)
        dry_run = (mode == "PAPER")

        active_market = kalshi_trader.get_active_15m_market(allow_synthetic=dry_run)
        if not active_market:
            logger.error("[ScalpEngine] No active Kalshi market is available; scalp order was not submitted.")
            return
        count = self.config.get("max_contracts", 1)
        result = kalshi_trader.place_order(
            ticker=active_market.get("ticker", ""),
            side=side,
            count=count,
            limit_price_dollars=None,  # Kalshi contract limit price, not BTC price!
            dry_run=dry_run,
        )
        if result.get("success"):
            trade_id = result.get("order_id", f"scalp_{int(time.time())}")
            contract_price = result.get("filled_price", 0.50)
            filled_count = float(result.get("fill_count", count) or 0) if not dry_run else float(count)
            if filled_count <= 0:
                logger.error("[ScalpEngine] Scalp order received no fill; no trade record was created.")
                return
            contract_cost = result.get("total_cost", round(contract_price * filled_count, 2))
            close_time = active_market.get("close_time", "")
            close_epoch = time.time() + self.config.get("interval_seconds", 900)
            if close_time:
                try:
                    close_epoch = datetime.fromisoformat(close_time.replace("Z", "+00:00")).timestamp()
                except (TypeError, ValueError):
                    pass

            if dry_run:
                try:
                    from backend.btc.paper_balance import update_balance
                    update_balance(-float(contract_cost))
                except Exception as e:
                    logger.error(f"[ScalpEngine] Paper balance deduction failed: {e}")

            entry_atr = 150.0
            try:
                from backend.btc.data_fetcher import fetch_candles
                from backend.btc.indicators import add_all_indicators
                df_c = fetch_candles("15m", limit=30)
                if df_c is not None and not df_c.empty:
                    df_ind = add_all_indicators(df_c)
                    if "atr" in df_ind.columns and len(df_ind["atr"]) > 0:
                        entry_atr = float(df_ind["atr"].iloc[-1])
            except Exception as e:
                logger.warning(f"[ScalpEngine] Could not fetch entry ATR, defaulting to 150.0: {e}")

            with self._trade_lock:
                self._active_trade = {
                    "id": trade_id,
                    "side": side.upper(),
                    "btc_entry_price": market_price,
                    "entry_atr": entry_atr,
                    "contract_price": contract_price,
                    "contract_count": filled_count,
                    "close_epoch": close_epoch,
                    "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime(
                        "%Y-%m-%d %I:%M:%S %p ET"
                    ),
                }
            # Append to AutoExecutor history for UI visibility
            auto_executor._save_trades_history(
                auto_executor.get_trades_history() + [
                    {
                        "id": trade_id,
                        "client_order_id": result.get("client_order_id", ""),
                        "timestamp": self._active_trade["timestamp"],
                        "interval_close_time": close_time,
                        "close_epoch": close_epoch,
                        "ticker": active_market.get("ticker", ""),
                        "title": "Scalp trade",
                        "strike": active_market.get("strike_price"),
                        "direction": "ABOVE" if side == "yes" else "BELOW",
                        "recommendation": "SCALP",
                        "conviction_grade": "SCALP",
                        "side": side.upper(),
                        "entry_price": contract_price,
                        "btc_price_at_entry": market_price,
                        "count": filled_count,
                        "cost": contract_cost,
                        "mode": mode,
                        "status": "OPEN",
                        "result": "PENDING",
                        "pnl": 0.0,
                        "catalysts": ["Scalp engine"],
                    }
                ]
            )
            logger.info(f"[ScalpEngine] Opened {side.upper()} scalp trade id={trade_id} @ contract price ${contract_price:.2f} (BTC ${market_price:.2f}, ATR ${entry_atr:.1f})")
            threading.Thread(target=self._monitor_trade, daemon=True).start()
        else:
            logger.error(f"[ScalpEngine] Trade failed: {result.get('error')}")

    def register_position(self, trade_record: Dict[str, Any]) -> None:
        """Register an active trade (from Auto-Rollover or Manual Execution) for scalp monitoring & early exit."""
        trade_id = trade_record.get("id")
        if not trade_id:
            return

        side = str(trade_record.get("side", "")).upper()
        market_price = float(trade_record.get("btc_price_at_entry") or trade_record.get("market_snapshot", {}).get("price") or 0.0)
        if market_price <= 0:
            from backend.btc.data_fetcher import get_btc_ticker
            market_price = float(get_btc_ticker().get("price", 0.0))

        entry_atr = 150.0
        try:
            from backend.btc.data_fetcher import fetch_candles
            from backend.btc.indicators import add_all_indicators
            df_c = fetch_candles("15m", limit=30)
            if df_c is not None and not df_c.empty:
                df_ind = add_all_indicators(df_c)
                if "atr" in df_ind.columns and len(df_ind["atr"]) > 0:
                    entry_atr = float(df_ind["atr"].iloc[-1])
        except Exception:
            pass

        trade_info = {
            "id": trade_id,
            "side": side,
            "btc_entry_price": market_price,
            "entry_atr": entry_atr,
            "contract_price": float(trade_record.get("entry_price", 0.50)),
            "contract_count": float(trade_record.get("count", 1)),
            "close_epoch": float(trade_record.get("close_epoch") or (time.time() + 900)),
            "timestamp": trade_record.get("timestamp", datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET")),
        }

        with self._trade_lock:
            self._active_trade = trade_info
            if not hasattr(self, "_active_positions"):
                self._active_positions = {}
            self._active_positions[trade_id] = trade_info

        logger.info(f"[ScalpEngine] Registered trade {trade_id} ({side}) for early scalp profit monitoring at BTC ${market_price:,.2f}")
        threading.Thread(target=self._monitor_position, args=(trade_id,), daemon=True).start()

    def _monitor_trade(self) -> None:
        if self._active_trade and self._active_trade.get("id"):
            self._monitor_position(self._active_trade["id"])

    def _monitor_position(self, trade_id: str) -> None:
        from backend.btc.auto_executor import auto_executor
        with self._trade_lock:
            if not hasattr(self, "_active_positions") or trade_id not in self._active_positions:
                trade = self._active_trade if (self._active_trade and self._active_trade.get("id") == trade_id) else None
            else:
                trade = self._active_positions[trade_id]

        if not trade:
            return

        profit_target = float(self.config.get("profit_target", 0.25) or 0.25)
        loss_target = float(self.config.get("loss_target", 0.25) or 0.25)
        take_profit_atr = float(self.config.get("take_profit_atr", 0.0) or 0.0)
        entry_atr = float(trade.get("entry_atr", 150.0) or 150.0)
        btc_entry = float(trade.get("btc_entry_price", 0.0) or 0.0)

        # Dynamic ATR-based Take Profit Target
        if take_profit_atr > 0 and entry_atr > 0 and btc_entry > 0:
            target_dollar_move = take_profit_atr * entry_atr
            profit_target = (target_dollar_move / btc_entry) * 100.0
            logger.info(f"[ScalpEngine] Dynamic Take-Profit Target active for {trade_id}: {take_profit_atr}x ATR (${target_dollar_move:.2f} move, {profit_target:.3f}%)")

        while True:
            with self._trade_lock:
                if hasattr(self, "_active_positions") and trade_id not in self._active_positions:
                    break
                if not hasattr(self, "_active_positions") and not self._active_trade:
                    break

            if time.time() > float(trade.get("close_epoch", float("inf"))) + 10:
                auto_executor.check_settlements()
                with self._trade_lock:
                    if hasattr(self, "_active_positions") and trade_id in self._active_positions:
                        del self._active_positions[trade_id]
                    if self._active_trade and self._active_trade.get("id") == trade_id:
                        self._active_trade.clear()
                break

            ticker = get_btc_ticker()
            price = float(ticker.get("price", 0.0))
            
            if trade["side"] == "YES":
                btc_pnl = price - btc_entry
            else:
                btc_pnl = btc_entry - price
                
            # Convert BTC price move to a percentage
            rel = (btc_pnl / btc_entry) * 100.0 if btc_entry != 0 else 0
            
            if rel >= profit_target or rel <= -loss_target:
                reason = "SCALP_PROFIT_TARGET" if rel >= profit_target else "SCALP_STOP_LOSS"
                logger.info(f"[ScalpEngine] Triggering early exit for {trade_id} ({reason}): BTC move {rel:+.3f}% (target: {profit_target:.3f}%)")

                # Calculate realistic contract price for paper/simulated trades
                entry_contract_price = float(trade.get("contract_price", 0.50) or 0.50)
                if reason == "SCALP_PROFIT_TARGET":
                    # Scalp win: contract gained substantial value before expiry (e.g. $0.50 -> ~$0.75)
                    estimated_exit = round(min(0.92, max(0.55, entry_contract_price + 0.25)), 4)
                else:
                    # Scalp loss: contract decayed/lost value before expiry (e.g. $0.50 -> ~$0.25)
                    estimated_exit = round(max(0.08, min(0.45, entry_contract_price - 0.25)), 4)

                close_res = auto_executor.close_specific_trade(trade_id, reason=reason, estimated_exit_price=estimated_exit)
                if not close_res.get("success"):
                    logger.warning(f"[ScalpEngine] Exit not filled for {trade_id}: {close_res.get('error')}")
                    time.sleep(1)
                    continue
                if close_res.get("closed"):
                    logger.info(f"[ScalpEngine] Successfully closed {trade_id} at market bid with P/L ${close_res.get('pnl', 0):.4f}")
                    with self._trade_lock:
                        if hasattr(self, "_active_positions") and trade_id in self._active_positions:
                            del self._active_positions[trade_id]
                        if self._active_trade and self._active_trade.get("id") == trade_id:
                            self._active_trade.clear()
                    break
                trade["contract_count"] = close_res.get("remaining_count", trade.get("contract_count", 0))
                logger.info(f"[ScalpEngine] Partial exit for {trade['id']}; {trade['contract_count']} contracts remain.")
            time.sleep(1)

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------
    def load_config(self) -> Dict[str, Any]:
        return self.config

    def save_config(self, new_cfg: Dict[str, Any]) -> None:
        self.config.update(new_cfg)
        self._save_config()

    def get_status(self) -> Dict[str, Any]:
        with self._trade_lock:
            active_copy = dict(self._active_trade)
        return {
            "enabled": self.enabled,
            "mode": self.config.get("mode", "PAPER"),
            "active_trade": active_copy,
            "last_trade_ts": self._last_trade_ts,
            "config": self.config
        }

# Global singleton instance
scalp_engine = ScalpEngine()
