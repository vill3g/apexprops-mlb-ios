"""
Investments Auto-Executor & Intraday Cycle Engine
Manages lifecycle for Robinhood Stocks, ETFs, and Options:
- Scans user's watchlist symbols
- Runs Agentic Desk evaluation
- Dispatches orders via RobinhoodClientFactory (Paper or Live)
- Tracks open positions and checks TP/SL, Dynamic Trailing Stops, and EOD Auto-Flattening (15:52 ET)
- Records trades in SQLite TradeStore with asset="INVESTMENTS" and metadata
"""

import datetime
import json
import logging
import os
import threading
import time
from typing import Dict, List, Optional, Any
from zoneinfo import ZoneInfo

from backend.database.models import (
    get_all_active_users,
    get_user_by_id,
    credit_user_investments_paper_balance
)
from backend.database.trade_store import TradeStore
from backend.investments.robinhood_client import (
    RobinhoodClientFactory,
    RobinhoodMarketSession,
    get_live_stock_quote,
    get_decision_quote,
    black_scholes_price
)
from backend.investments.live_ops import (
    DEAD_STATES,
    is_live,
    parse_meta,
    reconcile_live_trades,
    settle_paper_balance,
    submit_exit,
    trade_direction,
    update_meta
)
from backend.investments.risk_engine import RiskEngine
from backend.investments.agentic_desk import AgenticInvestmentsDesk
from backend.investments.market_screener import DynamicMarketScreener

logger = logging.getLogger(__name__)
NY_TZ = ZoneInfo("America/New_York")


class InvestmentsExecutor:
    """Autonomous intraday executor for the Investments Universe."""

    def __init__(self):
        self.desk = AgenticInvestmentsDesk()
        self._lock = threading.Lock()
        self._last_cycle_time = 0.0

    def run_cycle(self) -> Dict[str, Any]:
        """
        Executes one full iteration across all active users enabled for INVESTMENTS.
        Called on schedule (e.g. every 30s) by backend/worker.py.
        """
        with self._lock:
            now = time.time()
            session = RobinhoodMarketSession.get_current_session()
            active_users = get_all_active_users()

            eligible_users = []
            for u in active_users:
                universe = str(u.get("trading_universe") or "FINANCIAL").upper()
                ai_on = bool(u.get("ai_enabled", 1))
                if ai_on and any(x in universe for x in ("INVESTMENTS", "BOTH", "ALL")):
                    eligible_users.append(u)

            settled_count = 0
            opened_count = 0

            # 1. Manage active open positions (TP/SL, Trailing Stop, EOD Flatten)
            for u in eligible_users:
                uid = u["id"]
                s_count = self._monitor_and_manage_positions(uid, u, session)
                settled_count += s_count

            # 2. If market is in RTH and daytrading allowed, scan and execute new opportunities
            if session["can_daytrade"] and not session["is_flatten_window"]:
                for u in eligible_users:
                    uid = u["id"]
                    o_count = self._evaluate_and_execute_user(uid, u)
                    opened_count += o_count

            self._last_cycle_time = now
            return {
                "success": True,
                "timestamp": now,
                "session": session["state"],
                "eligible_users_count": len(eligible_users),
                "settled_count": settled_count,
                "opened_count": opened_count
            }

    def _monitor_and_manage_positions(
        self,
        user_id: int,
        user_config: Dict[str, Any],
        session: Dict[str, Any]
    ) -> int:
        """Monitors open investment trades for TP/SL, Trailing Stop, or EOD auto-flatten.

        Safety: never acts on placeholder (fallback) quotes; LIVE exits only during regular
        hours; EOD flatten only inside the 15:52-16:00 ET window; LIVE trades with a pending
        entry or an already-working exit order are skipped (no duplicate market orders)."""
        open_trades = TradeStore.get_open_trades(user_id)
        # Filter for investments universe trades
        inv_trades = [t for t in open_trades if str(t.get("asset") or "").upper() == "INVESTMENTS"]
        if not inv_trades:
            return 0

        settled = 0
        # EOD flatten only in the pre-close window on trading days (never after-hours / overnight)
        is_eod_window = bool(session.get("is_flatten_window"))
        rth_open = bool(session.get("is_open"))

        client = RobinhoodClientFactory.get_client(user_id, mode_override=user_config.get("trading_mode", "PAPER"))

        # Reconcile pending LIVE entries / exits with the broker first (read-only)
        if any(is_live(t) for t in inv_trades):
            try:
                reconcile_live_trades(user_id, client, inv_trades)
            except Exception as e:
                logger.warning(f"[InvestmentsExecutor] reconcile error user #{user_id}: {e}")
            inv_trades = [t for t in TradeStore.get_open_trades(user_id)
                          if str(t.get("asset") or "").upper() == "INVESTMENTS"]

        for t in inv_trades:
            ticker = t.get("ticker", "")
            meta = parse_meta(t)
            live = is_live(t)

            if live:
                if meta.get("pending_fill") or (meta.get("pending_close") or {}).get("order_id") and \
                        str((meta.get("pending_close") or {}).get("state") or "").lower() not in DEAD_STATES:
                    continue
                if not rth_open:
                    continue  # market orders outside RTH would queue for next open (gap risk)

            vehicle = meta.get("vehicle", "STOCK").upper()
            symbol = meta.get("symbol") or ticker.split("_")[0]
            entry_price = float(t.get("entry_price") or 0.0)
            if entry_price <= 0:
                continue
            count = float(t.get("count") or 1.0)
            direction = trade_direction(t)

            # Current price calculation (never on placeholder quotes)
            quote = get_decision_quote(symbol, client if live else None)
            if not quote:
                logger.warning(f"[InvestmentsExecutor] No usable quote for {symbol}; skipping TP/SL for {t.get('id')}")
                continue

            if vehicle == "STOCK":
                cur_price = float(quote["bid"] if direction > 0 else quote["ask"])
            else:
                # Option
                spot = float(quote["price"])
                strike = float(meta.get("strike") or spot)
                exp = str(meta.get("expiration") or "")
                o_type = str(meta.get("option_type") or "CALL")
                try:
                    exp_date = datetime.date.fromisoformat(exp)
                    today = datetime.datetime.now(NY_TZ).date()
                    dte = max((exp_date - today).days, 0)
                except Exception:
                    dte = 1
                theo_px, _, _ = black_scholes_price(spot=spot, strike=strike, dte_days=dte, option_type=o_type)
                cur_price = theo_px

            pnl_dollars = round((cur_price - entry_price) * count * (100 if vehicle == "OPTION" else 1) * direction, 2)
            pnl_pct = round(((cur_price - entry_price) / max(entry_price, 0.001)) * 100.0 * direction, 2)

            # Best price seen for trailing stop (high for longs, low for shorts) - persisted
            if direction > 0:
                best_seen = float(meta.get("highest_seen_price") or entry_price)
                improved = cur_price > best_seen
            else:
                best_seen = float(meta.get("lowest_seen_price") or entry_price)
                improved = cur_price < best_seen
            if improved:
                best_seen = cur_price
                key = "highest_seen_price" if direction > 0 else "lowest_seen_price"
                try:
                    update_meta(t, {key: best_seen})
                except Exception as e:
                    logger.debug(f"[InvestmentsExecutor] trailing persist failed: {e}")

            exit_reason = None

            # 1. EOD Auto-Flatten Window (15:52 ET)
            if is_eod_window and bool(user_config.get("investments_eod_auto_flatten", 1)):
                exit_reason = "EOD_AUTO_FLATTEN"

            # 2. Take Profit check
            tp_pct = float(meta.get("tp_pct") or (35.0 if vehicle == "OPTION" else 2.5))
            if pnl_pct >= tp_pct:
                exit_reason = "TAKE_PROFIT"

            # 3. Stop Loss check
            sl_pct = float(meta.get("sl_pct") or (20.0 if vehicle == "OPTION" else 1.0))
            if pnl_pct <= -sl_pct:
                exit_reason = "STOP_LOSS"

            # 4. Trailing Stop
            if bool(user_config.get("investments_trailing_stop_enabled", 1)) and not exit_reason:
                trail_pct = float(user_config.get("investments_trailing_stop_pct", 0.8))
                pullback_pct = ((best_seen - cur_price) / max(best_seen, 0.001)) * 100.0 * direction
                in_profit = (best_seen - entry_price) * direction > 0
                if in_profit and pullback_pct >= trail_pct:
                    exit_reason = "TRAILING_STOP"

            if exit_reason:
                if self._settle_investment_trade(
                    user_id=user_id,
                    trade=t,
                    cur_price=cur_price,
                    pnl_dollars=pnl_dollars,
                    exit_reason=exit_reason,
                    client=client
                ):
                    settled += 1

        return settled

    def _settle_investment_trade(
        self,
        user_id: int,
        trade: Dict[str, Any],
        cur_price: float,
        pnl_dollars: float,
        exit_reason: str,
        client: Any
    ) -> bool:
        """Closes and settles an investment position. Returns True only when closed locally.

        LIVE: sends the real opposite-side order and closes locally only on a confirmed broker
        fill (at the broker fill price); queued orders are tracked via metadata.pending_close."""
        trade_id = trade["id"]
        mode = str(trade.get("mode") or "PAPER").upper()
        count = float(trade.get("count") or 1.0)
        meta = parse_meta(trade)
        vehicle = meta.get("vehicle", "STOCK").upper()

        if mode != "PAPER":
            res = submit_exit(user_id, trade, client, exit_reason)
            if res.get("status") == "CLOSED":
                logger.info(f"[InvestmentsExecutor] LIVE closed #{user_id} {trade_id} ({exit_reason}) @ {res.get('exit_price')}: PnL ${res.get('pnl'):+.2f}")
                return bool(res.get("closed"))
            if res.get("status") == "PENDING_CLOSE":
                logger.info(f"[InvestmentsExecutor] LIVE exit pending #{user_id} {trade_id} ({exit_reason}) order={res.get('order_id')} state={res.get('broker_state')}")
            else:
                logger.error(f"[InvestmentsExecutor] LIVE exit FAILED #{user_id} {trade_id} ({exit_reason}): {res.get('error')}")
            return False

        now_ny = datetime.datetime.now(NY_TZ).isoformat()
        close_update = {
            "status": "CLOSED",
            "exit_price": cur_price,
            "pnl": pnl_dollars,
            "pnl_dollars": pnl_dollars,
            "exit_reason": exit_reason,
            "settled_at": time.time(),
            "closed_at": now_ny
        }

        if TradeStore.close_if_open(user_id, trade, close_update):
            settle_paper_balance(user_id, trade, cur_price)
            logger.info(f"[InvestmentsExecutor] Closed #{user_id} {trade_id} ({exit_reason}): PnL ${pnl_dollars:+.2f}")
            return True
        return False

    def _evaluate_and_execute_user(self, user_id: int, user_config: Dict[str, Any]) -> int:
        """Evaluates scanner opportunities and enters trade for a user if within limits."""
        # Check max concurrent open positions limit
        max_open = int(user_config.get("investments_max_open_positions", 4))
        open_trades = [t for t in TradeStore.get_open_trades(user_id) if str(t.get("asset") or "").upper() == "INVESTMENTS"]
        if len(open_trades) >= max_open:
            return 0

        # Check max daily trades (today's NY date only)
        max_daily_trades = int(user_config.get("investments_max_daily_trades", 8))
        today_ny = datetime.datetime.now(NY_TZ).date().isoformat()
        recent = [t for t in TradeStore.get_recent_trades(user_id, limit=200)
                  if str(t.get("asset") or "").upper() == "INVESTMENTS"
                  and str(t.get("timestamp") or "")[:10] == today_ny]
        if len(recent) >= max_daily_trades:
            return 0

        mode = str(user_config.get("trading_mode", "PAPER")).upper()
        is_live_mode = mode == "LIVE"

        # Evaluate Institutional Risk Engine Gates
        risk_ok, risk_reason = RiskEngine.evaluate_new_order_safety(
            user_id=user_id,
            cost=0.0,
            is_live=is_live_mode,
            equity=float(user_config.get("investments_paper_balance") or 10000.0)
        )
        if not risk_ok:
            logger.info(f"[InvestmentsExecutor] RiskEngine blocked entry for user #{user_id}: {risk_reason}")
            return 0
        if is_live_mode and not RobinhoodMarketSession.get_current_session().get("can_daytrade"):
            return 0  # LIVE entries only during regular hours (outside the flatten window)

        client = RobinhoodClientFactory.get_client(user_id, mode_override=user_config.get("trading_mode", "PAPER"))
        bp_info = client.get_buying_power()
        if is_live_mode and not bp_info.get("success"):
            logger.warning(f"[InvestmentsExecutor] LIVE buying power unavailable for user #{user_id}; skipping entries.")
            return 0
        buying_power = float(bp_info.get("buying_power") or 0.0)
        if is_live_mode and buying_power < 1.0:
            return 0

        # Resolve tradeable symbols via DynamicMarketScreener (WATCHLIST_ONLY, DYNAMIC_SCREENER, or HYBRID)
        candidate_symbols = DynamicMarketScreener.resolve_tradeable_symbols(user_config)

        # Filter out symbols already open
        open_symbols = set()
        for t in open_trades:
            meta = t.get("metadata") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            sym = meta.get("symbol") or t.get("ticker", "").split("_")[0]
            open_symbols.add(sym.upper())

        available_symbols = [s for s in candidate_symbols if s not in open_symbols]
        if not available_symbols:
            return 0

        opened = 0
        for sym in available_symbols:
            opp = self.desk.evaluate_opportunity(sym, user_config, buying_power)
            if opp.get("decision") == "EXECUTE":
                sizing = opp.get("sizing", {})
                vehicle = sizing.get("vehicle", "STOCK")
                cost = sizing.get("cost_total", 0.0)

                if is_live_mode:
                    try:
                        cost_f = float(cost or 0.0)
                    except (TypeError, ValueError):
                        cost_f = 0.0
                    cost_ok, cost_reason = RiskEngine.evaluate_new_order_safety(
                        user_id=user_id,
                        cost=cost_f,
                        is_live=True,
                        equity=buying_power
                    )
                    if not cost_ok:
                        logger.info(f"[InvestmentsExecutor] RiskEngine cost block {sym}: {cost_reason}")
                        continue
                    if cost_f < 1.0 or cost_f > buying_power:
                        logger.info(f"[InvestmentsExecutor] LIVE skip {sym}: cost ${cost_f:.2f} vs BP ${buying_power:.2f} (min $1)")
                        continue
                    if not get_decision_quote(sym, client):
                        logger.warning(f"[InvestmentsExecutor] LIVE skip {sym}: no usable quote")
                        continue
                # Order submission
                if vehicle == "OPTION":
                    res = client.place_option_order(
                        symbol=sym,
                        strike=sizing["strike"],
                        expiration=sizing["expiration"],
                        option_type=sizing["option_type"],
                        action="BUY",
                        contracts=sizing["contracts"]
                    )
                    count_val = sizing["contracts"]
                    ticker_val = sizing["contract_ticker"]
                    entry_px = sizing["price_per_contract"]
                else:
                    res = client.place_stock_order(
                        symbol=sym,
                        action="BUY",
                        shares=sizing["shares"]
                    )
                    count_val = sizing["shares"]
                    ticker_val = sym
                    entry_px = sizing["price"]

                if res.get("success"):
                    trade_id = res.get("order_id")
                    if not trade_id:
                        if is_live_mode:
                            logger.error(f"[InvestmentsExecutor] LIVE order for {sym} succeeded without order_id; refusing to record phantom trade.")
                            continue
                        trade_id = f"RH-INV-{sym}-{int(time.time()*1000)}"
                    now_ny = datetime.datetime.now(NY_TZ).isoformat()
                    broker_state = str(res.get("state") or res.get("status") or "").lower()
                    pending_fill = is_live_mode and not (broker_state == "filled" and res.get("filled_price"))
                    if is_live_mode and res.get("filled_price"):
                        entry_px = float(res["filled_price"])
                    if is_live_mode and res.get("shares") and vehicle != "OPTION":
                        count_val = float(res["shares"])
                    # Attach Smart Bracket OCO levels for automated trade exit
                    tp_target_px = round(entry_px * (1.0 + (float(sizing.get("tp_pct") or 2.5) / 100.0)), 2)
                    sl_target_px = round(entry_px * (1.0 - (float(sizing.get("sl_pct") or 1.0) / 100.0)), 2)
                    meta_payload = {
                        "universe": "INVESTMENTS",
                        "vehicle": vehicle,
                        "symbol": sym,
                        "setup_type": opp.get("setup_type"),
                        "bias": opp.get("bias"),
                        "confidence": opp.get("confidence"),
                        "dossier": opp.get("dossier"),
                        "sizing": sizing,
                        "tp_pct": sizing.get("tp_pct"),
                        "sl_pct": sizing.get("sl_pct"),
                        "tp_target_price": tp_target_px,
                        "sl_target_price": sl_target_px,
                        "smart_bracket_active": True,
                        "highest_seen_price": entry_px,
                        "broker_state": broker_state or None,
                        "pending_fill": bool(pending_fill),
                        "estimated_entry": bool(pending_fill)
                    }
                    if vehicle == "OPTION":
                        meta_payload.update({
                            "strike": sizing.get("strike"),
                            "expiration": sizing.get("expiration"),
                            "option_type": sizing.get("option_type")
                        })

                    trade_rec = {
                        "id": trade_id,
                        "user_id": user_id,
                        "ticker": ticker_val,
                        "side": "BUY",
                        "direction": opp.get("bias"),
                        "entry_price": entry_px,
                        "count": count_val,
                        "status": "OPEN",
                        "pnl": 0.0,
                        "mode": user_config.get("trading_mode", "PAPER"),
                        "reason": f"AI Desk ({opp.get('setup_type')} • {opp.get('bias')})",
                        "trading_style": "INTRADAY_AGENTIC",
                        "signal_source": "GEMINI_AGENTIC_DESK",
                        "timestamp": now_ny,
                        "asset": "INVESTMENTS",
                        "metadata": json.dumps(meta_payload),
                        "ml_reasoning": json.dumps(opp.get("dossier") or {})
                    }
                    TradeStore.insert_trade(user_id, trade_rec)
                    logger.info(f"[InvestmentsExecutor] Opened trade for User #{user_id}: {trade_id} on {ticker_val} (${cost:.2f})")
                    opened += 1
                    break  # Open 1 position per cycle per user to prevent over-allocation

        return opened
