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
                            side = "yes" if pct_change > 0 else "no"
                            self._execute_trade(side, current_price)
                            self._last_trade_ts = now
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
        result = kalshi_trader.place_order(
            ticker=kalshi_trader.get_active_15m_market().get("ticker", ""),
            side=side,
            count=self.config.get("max_contracts", 1),
            limit_price_dollars=market_price,
            dry_run=dry_run,
        )
        if result.get("success"):
            trade_id = result.get("order_id", f"scalp_{int(time.time())}")
            self._active_trade = {
                "id": trade_id,
                "side": side.upper(),
                "entry_price": market_price,
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
                        "entry_price": market_price,
                        "count": self.config.get("max_contracts", 1),
                        "cost": round(market_price * self.config.get("max_contracts", 1), 4),
                        "mode": mode,
                        "status": "OPEN",
                        "result": "PENDING",
                        "pnl": 0.0,
                        "catalysts": ["Scalp engine"],
                    }
                ]
            )
            print(f"[ScalpEngine] Opened {side.upper()} scalp trade id={trade_id}")
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
            ticker = get_btc_ticker()
            price = float(ticker.get("price", 0.0))
            entry = trade["entry_price"]
            if trade["side"] == "YES":
                pnl = price - entry
            else:
                pnl = entry - price
            rel = pnl / entry if entry != 0 else 0
            if rel >= profit_target or rel <= -loss_target:
                # close via AutoExecutor helper (to be added)
                auto_executor.close_specific_trade(trade["id"], pnl)
                print(f"[ScalpEngine] Closed trade {trade['id']} with P/L {pnl:.4f}")
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
