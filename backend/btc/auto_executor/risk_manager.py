
import logging

logger = logging.getLogger(__name__)
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

try:
    from zoneinfo import ZoneInfo
except ImportError:
    pass


from backend.btc.backtest import analyze_calibration_overconfidence
from backend.btc.ml_engine import get_ml_engine

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data")
HISTORY_FILE = os.path.join(DATA_DIR, "trades_history.json")
CONFIG_FILE = os.path.join(DATA_DIR, "trading_config.json")

class RiskManagerMixin:
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

            # Circuit Breaker: Halt trading after 3 consecutive losses
            consecutive_losses = 0
            sorted_today = sorted(today_trades, key=lambda x: str(x.get("timestamp", "")))
            for t in reversed(sorted_today):
                if t.get("status") in ["SETTLED", "CLOSED"]:
                    if float(t.get("pnl", 0.0)) < 0.0:
                        consecutive_losses += 1
                        if consecutive_losses >= 3:
                            return "Circuit Breaker Activated: 3 consecutive losing trades. Halting to protect capital."
                    elif float(t.get("pnl", 0.0)) > 0.0:
                        break  # Found a winning trade, safe to continue
            return None

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
    
            min_bucket = max(3, min_samples // 15)
            drift_detected, reason = analyze_calibration_overconfidence(calibration_table, min_bucket_count=min_bucket)
    
            if drift_detected:
                logger.warning(f"[AutoExecutor] Live calibration drift detected: {reason}. Triggering ML model retraining.")
                try:
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



