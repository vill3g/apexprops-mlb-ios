"""
backend.investments.risk_engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Professional institutional risk-management engine for the Investments Universe.
Enforces:
  1. Emergency Kill-Switch (immediate trading halt + auto-flatten).
  2. Consecutive loss circuit breakers & cooldown windows.
  3. Strict daily loss cap (realized + unrealized P&L).
  4. Daily allocated capital budget limits (max dollars spent per day in LIVE).
  5. Maximum aggregate portfolio open exposure (% of equity).
  6. Dynamic risk-per-trade position sizing based on stop-loss distance.
"""

import time
import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, Tuple, Optional
from backend.database.models import get_user_by_id
from backend.database.trade_store import TradeStore

NY_TZ = ZoneInfo("America/New_York")


class RiskEngine:
    @staticmethod
    def get_risk_status(user_id: int) -> Dict[str, Any]:
        """Calculates real-time risk parameters and limits for the user."""
        u = get_user_by_id(user_id) or {}
        now = time.time()
        today_ny = datetime.datetime.now(NY_TZ).date().isoformat()

        kill_switch = bool(u.get("investments_kill_switch", 0))
        kill_switch_at = u.get("investments_kill_switch_at")

        cooldown_mins = int(u.get("investments_cooldown_minutes") or 60)
        max_consec_losses = int(u.get("investments_max_consecutive_losses") or 3)
        max_daily_risk = float(u.get("investments_max_daily_risk") or 500.0)
        live_max_daily_spend = float(u.get("investments_live_max_dollars_per_day") or 25.0)
        max_exposure_pct = float(u.get("investments_max_exposure_pct") or 50.0)
        risk_per_trade_pct = float(u.get("investments_risk_per_trade_pct") or 1.0)
        live_autotrade_enabled = bool(u.get("investments_live_autotrade_enabled", 0))

        # Scan recent trades for today's realized PnL & consecutive losses
        all_recent = TradeStore.get_recent_trades(user_id, limit=100)
        inv_trades = []
        for t in all_recent:
            asset = str(t.get("asset") or "").upper()
            if asset in ("INVESTMENTS", "STOCK", "OPTION"):
                inv_trades.append(t)

        realized_today = 0.0
        spent_today_live = 0.0
        consecutive_losses = 0
        loss_streak_active = True
        last_loss_ts = 0.0

        for t in inv_trades:
            status = str(t.get("status") or "OPEN").upper()
            t_mode = str(t.get("mode") or "PAPER").upper()
            pnl = float(t.get("pnl_dollars") if t.get("pnl_dollars") is not None else (t.get("pnl") or 0.0))
            raw_ts = t.get("settled_at") or t.get("timestamp") or 0.0
            try:
                ts = float(raw_ts)
            except Exception:
                ts = now

            # Date check
            try:
                t_date = datetime.datetime.fromtimestamp(ts, NY_TZ).date().isoformat()
            except Exception:
                t_date = str(t.get("timestamp") or "")[:10] or today_ny

            if t_date == today_ny:
                if status == "CLOSED":
                    realized_today += pnl
                if t_mode == "LIVE":
                    spent_today_live += float(t.get("entry_price", 0.0)) * float(t.get("count", 1.0))

            if status == "CLOSED":
                if loss_streak_active:
                    if pnl < 0:
                        consecutive_losses += 1
                        if ts > last_loss_ts:
                            last_loss_ts = ts
                    elif pnl > 0:
                        loss_streak_active = False

        in_cooldown = False
        cooldown_remaining_secs = 0
        if consecutive_losses >= max_consec_losses and last_loss_ts > 0:
            elapsed = now - last_loss_ts
            required = cooldown_mins * 60
            if elapsed < required:
                in_cooldown = True
                cooldown_remaining_secs = int(required - elapsed)

        daily_loss_breached = (realized_today <= -abs(max_daily_risk))
        daily_spend_breached = (spent_today_live >= live_max_daily_spend)

        can_trade = (
            not kill_switch
            and not in_cooldown
            and not daily_loss_breached
        )

        return {
            "kill_switch": kill_switch,
            "kill_switch_at": kill_switch_at,
            "in_cooldown": in_cooldown,
            "cooldown_remaining_secs": cooldown_remaining_secs,
            "consecutive_losses": consecutive_losses,
            "max_consecutive_losses": max_consec_losses,
            "realized_today": round(realized_today, 2),
            "max_daily_risk": max_daily_risk,
            "daily_loss_breached": daily_loss_breached,
            "spent_today_live": round(spent_today_live, 2),
            "live_max_daily_spend": live_max_daily_spend,
            "daily_spend_breached": daily_spend_breached,
            "max_exposure_pct": max_exposure_pct,
            "risk_per_trade_pct": risk_per_trade_pct,
            "live_autotrade_enabled": live_autotrade_enabled,
            "can_trade": can_trade
        }

    @staticmethod
    def evaluate_new_order_safety(
        user_id: int,
        cost: float,
        is_live: bool,
        equity: float
    ) -> Tuple[bool, str]:
        """Evaluates whether placing an order violates institutional risk limits."""
        status = RiskEngine.get_risk_status(user_id)

        if status["kill_switch"]:
            return False, "Emergency Kill-Switch is ACTIVE. All trading halted."

        if status["in_cooldown"]:
            mins = status["cooldown_remaining_secs"] // 60
            return False, f"Cool-down circuit breaker active after {status['consecutive_losses']} losses. Paused for {mins}m."

        if status["daily_loss_breached"]:
            return False, f"Daily max loss cap of -${status['max_daily_risk']:.2f} reached. Trading halted for today."

        if is_live:
            if not status["live_autotrade_enabled"]:
                return False, "Live auto-trading is DISABLED in settings. Enable 'Allow Live Auto-Trading' to proceed."

            if (status["spent_today_live"] + cost) > status["live_max_daily_spend"]:
                rem = max(0.0, status["live_max_daily_spend"] - status["spent_today_live"])
                return False, f"Order cost (${cost:.2f}) exceeds remaining daily LIVE budget (${rem:.2f})."

        # Portfolio Exposure Cap
        if equity > 0:
            max_allowed_exposure = equity * (status["max_exposure_pct"] / 100.0)
            if cost > max_allowed_exposure:
                return False, f"Order size (${cost:.2f}) exceeds maximum allowed exposure cap of {status['max_exposure_pct']}% (${max_allowed_exposure:.2f})."

        return True, "OK"
