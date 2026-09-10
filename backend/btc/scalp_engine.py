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

    # ------------------------------------------------------------------
    # Config handling
    # ------------------------------------------------------------------
    def _load_config(self) -> None:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            # default config
            self.config = {
                "enabled": False,
                "mode": "PAPER",
                "price_move_threshold": 0.5,
                "profit_target": 0.25,
                "loss_target": 0.25,
                "max_contracts": 1,
                "max_trades_per_interval": 1,
                "interval_seconds": 900  # 15 minutes
            }
            self._save_config()

    def _save_config(self) -> None:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

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
        last_price = None
        while not self._stop_event.is_set():
            try:
                ticker = get_btc_ticker()
                current_price = float(ticker.get("price", 0.0))
                if last_price is not None:
                    pct_change = ((current_price - last_price) / last_price) * 100.0
                    if abs(pct_change) >= self.config.get("price_move_threshold", 0.5):
                        # enforce 1 trade per interval
                        now = time.time()
                        interval = self.config.get("interval_seconds", 900)
                        if now - self._last_trade_ts >= interval:
                            # Verify high confidence with BTC analyzer
                            try:
                                from backend.main import get_cached_btc_analysis
                                _, analysis = get_cached_btc_analysis()
                                
                                next_forecast = analysis.get("target_benchmark", {}).get("next_contract_forecast", {})
                                grade = next_forecast.get("conviction_grade", "D")
                                min_conviction = self.config.get("minimum_conviction", "A+")
                                
                                grade_hierarchy = {"A+": 4, "A": 3, "B+": 2, "B": 1, "C": 0, "D": -1}
                                current_grade_val = grade_hierarchy.get(grade, -1)
                                min_grade_val = grade_hierarchy.get(min_conviction, 4)
                                
                                if current_grade_val >= min_grade_val:
                                    # Ensure direction aligns with analyzer
                                    analyzer_dir = next_forecast.get("direction", "PASS")
                                    side = "yes" if pct_change > 0 else "no"
                                    
                                    if (side == "yes" and analyzer_dir == "ABOVE") or (side == "no" and analyzer_dir == "BELOW"):
                                        self._execute_trade(side, current_price)
                                        self._last_trade_ts = now
                                    else:
                                        print(f"[ScalpEngine] Blocked: Scalp direction '{side}' opposes analyzer '{analyzer_dir}'")
                                else:
                                    print(f"[ScalpEngine] Blocked: Conviction {grade} < min {min_conviction}")
                            except Exception as e:
                                print(f"[ScalpEngine] Analyzer check failed: {e}")
                last_price = current_price
            except Exception as e:
                print(f"[ScalpEngine] Monitoring error: {e}")
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
        
        count = self.config.get("max_contracts", 1)
        result = kalshi_trader.place_order(
            ticker=kalshi_trader.get_active_15m_market().get("ticker", ""),
            side=side,
            count=count,
            limit_price_dollars=None,  # Kalshi contract limit price, not BTC price!
            dry_run=dry_run,
        )
        if result.get("success"):
            trade_id = result.get("order_id", f"scalp_{int(time.time())}")
            contract_price = result.get("filled_price", 0.50)
            contract_cost = result.get("total_cost", round(contract_price * count, 2))
            
            self._active_trade = {
                "id": trade_id,
                "side": side.upper(),
                "btc_entry_price": market_price,
                "contract_price": contract_price,
                "contract_count": count,
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
                        "interval_close_time": kalshi_trader.get_active_15m_market().get(
                            "close_time", ""
                        ),
                        "ticker": kalshi_trader.get_active_15m_market().get("ticker", ""),
                        "title": "Scalp trade",
                        "strike": kalshi_trader.get_active_15m_market().get("strike_price"),
                        "direction": "ABOVE" if side == "yes" else "BELOW",
                        "recommendation": "SCALP",
                        "conviction_grade": "SCALP",
                        "side": side.upper(),
                        "entry_price": contract_price,
                        "btc_price_at_entry": market_price,
                        "count": count,
                        "cost": contract_cost,
                        "mode": mode,
                        "status": "OPEN",
                        "result": "PENDING",
                        "pnl": 0.0,
                        "catalysts": ["Scalp engine"],
                    }
                ]
            )
            print(f"[ScalpEngine] Opened {side.upper()} scalp trade id={trade_id} @ contract price ${contract_price:.2f} (BTC ${market_price:.2f})")
            threading.Thread(target=self._monitor_trade, daemon=True).start()
        else:
            print(f"[ScalpEngine] Trade failed: {result.get('error')}")

    def _monitor_trade(self) -> None:
        from backend.btc.auto_executor import auto_executor
        trade = self._active_trade
        if not trade:
            return
        profit_target = self.config.get("profit_target", 0.25)
        loss_target = self.config.get("loss_target", 0.25)
        while True:
            if not self._active_trade:
                break
            ticker = get_btc_ticker()
            price = float(ticker.get("price", 0.0))
            btc_entry = trade["btc_entry_price"]
            
            if trade["side"] == "YES":
                btc_pnl = price - btc_entry
            else:
                btc_pnl = btc_entry - price
                
            # Convert BTC price move to a percentage (e.g., 0.25 means 0.25%)
            rel = (btc_pnl / btc_entry) * 100.0 if btc_entry != 0 else 0
            
            if rel >= profit_target or rel <= -loss_target:
                contract_price = trade.get("contract_price", 0.50)
                count = trade.get("contract_count", 1)
                
                # Calculate real dollar PNL based on Kalshi contract size
                if rel >= profit_target:
                    dollar_pnl = (1.00 - contract_price) * count
                else:
                    dollar_pnl = -contract_price * count

                # close via AutoExecutor helper
                auto_executor.close_specific_trade(trade["id"], dollar_pnl)
                print(f"[ScalpEngine] Closed trade {trade['id']} with P/L ${dollar_pnl:.4f}")
                
                # Update paper balance if in PAPER mode
                if self.config.get("mode", auto_executor.mode) == "PAPER":
                    from backend.btc.paper_balance import update_balance
                    update_balance(dollar_pnl)

                self._active_trade.clear()
                break
            time.sleep(1)

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------
    def load_config(self) -> Dict[str, Any]:
        return self.config

    def save_config(self, new_cfg: Dict[str, Any]) -> None:
        self.config.update(new_cfg)
        self._save_config()

# Global singleton instance
scalp_engine = ScalpEngine()
