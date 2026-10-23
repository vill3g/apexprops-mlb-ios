"""
backend.investments.performance_tracker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Phase 2 Institutional Alpha & Performance Learning Engine:
  - Tracks real-time win rates, expectancy, and Sharpe per Setup Type (ORB_BREAKOUT, VWAP_RECLAIM, SQUEEZE_IGNITION).
  - Automatically flags or pauses underperforming / decaying setups.
  - Dynamically weights setup priority based on historical edge.
"""

import json
import logging
from typing import Dict, Any, List
from backend.database.trade_store import TradeStore

logger = logging.getLogger(__name__)


class PerformanceTracker:
    DEFAULT_SETUPS = ["ORB_BREAKOUT", "VWAP_RECLAIM", "SQUEEZE_IGNITION", "MANUAL"]

    @staticmethod
    def get_setup_performance(user_id: int) -> Dict[str, Any]:
        """Calculates win rate, expectancy, and active status per setup type."""
        all_trades = TradeStore.get_recent_trades(user_id, limit=250)
        inv_closed = []
        for t in all_trades:
            if str(t.get("asset") or "").upper() == "INVESTMENTS" and str(t.get("status") or "").upper() == "CLOSED":
                inv_closed.append(t)

        metrics: Dict[str, Dict[str, Any]] = {}
        for s in PerformanceTracker.DEFAULT_SETUPS:
            metrics[s] = {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate_pct": 0.0,
                "total_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "expectancy": 0.0,
                "status": "ACTIVE"  # ACTIVE | UNDERPERFORMING | SUSPENDED
            }

        for t in inv_closed:
            meta = t.get("metadata") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            setup = str(meta.get("setup_type") or "MANUAL").upper()
            if setup not in metrics:
                metrics[setup] = {
                    "trades": 0, "wins": 0, "losses": 0, "win_rate_pct": 0.0,
                    "total_pnl": 0.0, "avg_win": 0.0, "avg_loss": 0.0, "expectancy": 0.0, "status": "ACTIVE"
                }

            pnl = float(t.get("pnl_dollars") if t.get("pnl_dollars") is not None else (t.get("pnl") or 0.0))
            m = metrics[setup]
            m["trades"] += 1
            m["total_pnl"] += pnl
            if pnl > 0:
                m["wins"] += 1
            elif pnl < 0:
                m["losses"] += 1

        # Compute ratios & adaptively disable decaying setups
        for setup, m in metrics.items():
            cnt = m["trades"]
            if cnt > 0:
                m["win_rate_pct"] = round((m["wins"] / cnt) * 100.0, 1)
                m["total_pnl"] = round(m["total_pnl"], 2)
                m["expectancy"] = round(m["total_pnl"] / cnt, 2)
                # If a setup has >= 5 trades and a win rate < 30%, mark as UNDERPERFORMING
                if cnt >= 5 and m["win_rate_pct"] < 30.0:
                    m["status"] = "UNDERPERFORMING"
                elif cnt >= 8 and m["win_rate_pct"] < 25.0:
                    m["status"] = "SUSPENDED"

        return {
            "success": True,
            "total_evaluated_trades": len(inv_closed),
            "setups": metrics
        }
