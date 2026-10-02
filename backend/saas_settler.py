import json
import logging
import os
import threading
import time
import uuid

from backend.auth.security import decrypt_kalshi_key
from backend.btc.fees import kalshi_order_fee, net_pnl
from backend.btc.kalshi_client import get_kalshi_15m_market
from backend.btc.kalshi_trader import (
    PAPER_LATENCY_TAX_DOLLARS,
    KalshiTrader,
    filled_count as _filled_count,
)
from backend.btc.kalshi_trader import (
    kalshi_trader as paper_kalshi_trader,  # only ever used with dry_run=True here
)
from backend.database.models import (DATA_DIR, credit_user_paper_balance,
                                     deduct_user_paper_balance,
                                     get_all_active_users, get_user_lock)

logger = logging.getLogger(__name__)

def _fresh_quote(ticker, cache):
    """Fresh executable quote for one market (cached for the rest of this settlement pass)."""
    if ticker in cache:
        return cache[ticker]
    from backend.btc.kalshi_trader import kalshi_trader
    q = kalshi_trader.get_market_quote(ticker)
    cache[ticker] = q if q.get("success") else None
    return cache[ticker]


def _position_avg_price(ap, qty):
    """Average entry price of a Kalshi position, if the API gives enough to compute it."""
    for key in ("market_exposure_dollars", "total_cost_dollars"):
        try:
            v = float(ap.get(key))
            if qty > 0 and v > 0:
                return round(v / qty, 4)
        except (TypeError, ValueError):
            pass
    try:
        v = float(ap.get("market_exposure"))  # cents
        if qty > 0 and v > 0:
            return round(v / 100.0 / qty, 4)
    except (TypeError, ValueError):
        pass
    return None


# Only markets this bot trades are synced. Positions a user holds in other Kalshi
# markets (sports, politics, parlays...) are theirs to manage and are ignored.
BOT_SERIES_PREFIXES = ("KXBTC15M-", "KXETH15M-")


def _is_bot_market(ticker) -> bool:
    return str(ticker or "").upper().startswith(BOT_SERIES_PREFIXES)


def _series_of(ticker) -> str:
    """'KXETH15M-26SEP281015-15' -> 'KXETH15M'. Empty for markets this bot doesn't trade."""
    t = str(ticker or "").upper()
    return t.split("-", 1)[0] if _is_bot_market(t) else ""


def _market_for_ticker(ticker, cache: dict):
    """The active 15-minute market of the trade's OWN series (BTC, ETH...), fetched once per
    series per pass. Audit H3: the settler used to fetch only the default BTC market, so every
    ETH trade looked like "not the current market" - its stop-loss, take-profit and trailing
    stop never ran and it could only ever settle at expiry."""
    series = _series_of(ticker)
    if not series:
        return None
    if series not in cache:
        try:
            cache[series] = get_kalshi_15m_market(series_ticker=series) or None
        except Exception as e:
            logger.warning(f"[SaaSSettler] Could not fetch active {series} market: {e}")
            cache[series] = None
    return cache[series]


def _drop_synced_foreign_positions(user_id, trades) -> bool:
    """Close (with no P&L) OPEN sync records for markets the bot doesn't trade;
    an earlier version imported every Kalshi position on the account."""
    from backend.database.trade_store import TradeStore
    changed = False
    for t in trades:
        if (t.get("status") == "OPEN" and t.get("manual_sync")
                and not _is_bot_market(t.get("ticker"))):
            if TradeStore.close_if_open(user_id, t, {
                "exit_reason": "IGNORED_NON_BOT_MARKET", "pnl": 0.0,
                "exit_price": t.get("entry_price"), "settled_at": time.time(),
            }):
                t["status"] = "CLOSED"
                t["exit_reason"] = "IGNORED_NON_BOT_MARKET"
                changed = True
                logger.info(f"[SaaSSettler] Stopped tracking non-bot market {t.get('ticker')} for user {user_id}")
    return changed


def _sync_untracked_kalshi_positions(user, user_id, kt, trades) -> bool:
    """Record positions on the user's Kalshi account that the bot has no trade for.

    Safety rules (a previous version created a new record â€” and a real stop-loss sell â€”
    every ~1.5 s for one position):
      * one deterministic record id per (ticker, side), inserted with INSERT OR IGNORE,
        so the same position can never be recorded twice;
      * the "already tracked?" check queries SQLite directly and skips the sync if the
        database can't be read (it used to treat a read error as "not tracked");
      * synced records are flagged manual_sync and are never auto-sold by the bot.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from backend.database.models import get_db_connection
    from backend.database.trade_store import TradeStore

    modified = _drop_synced_foreign_positions(user_id, trades)
    pos_resp = kt.get_positions()
    if not pos_resp.get("success"):
        return modified
    for ap in pos_resp.get("positions", []):
        ap_ticker = ap.get("ticker")
        if not ap_ticker or not _is_bot_market(ap_ticker):
            continue
        for side in ("YES", "NO"):
            qty = kt._extract_side_position(ap, side)
            if qty <= 0:
                continue
            try:
                row = get_db_connection().execute(
                    "SELECT 1 FROM trades WHERE user_id = ? AND ticker = ? AND UPPER(side) = ? LIMIT 1",
                    (user_id, ap_ticker, side),
                ).fetchone()
            except Exception as e:
                logger.warning(f"[SaaSSettler] Skipping Kalshi sync for {user.get('username')}: DB read failed ({e})")
                return modified
            if row is not None or any(t.get("ticker") == ap_ticker and str(t.get("side", "")).upper() == side for t in trades):
                continue
            from backend.btc import inflight_orders
            inflight = inflight_orders.lookup(user_id, ap_ticker, side)
            if inflight and inflight["state"] == "pending":
                continue  # the bot just bought this and is writing its own record
            avg = _position_avg_price(ap, qty)
            record = {
                "id": f"sync_{ap_ticker}_{side}",
                "timestamp": datetime.now(ZoneInfo("America/New_York")).isoformat(),
                "ticker": ap_ticker,
                "direction": side,
                "side": side,
                "entry_price": avg if avg is not None else 0.50,
                "entry_estimated": avg is None,
                "count": qty,
                "status": "OPEN",
                "mode": "LIVE",
                "pnl": 0.0,
                "reason": "MANUAL_KALSHI_SYNC",
                "manual_sync": True,
                "trading_style": "MANUAL",
                "signal_source": "MANUAL",
            }
            if inflight:
                # The bot's order timed out without a confirmed fill, but it did fill:
                # record it as the bot's trade so it is labeled and managed as one.
                labels = inflight.get("labels") or {}
                record.update({
                    "reason": labels.get("reason") or "AI_COPY (AUTO)",
                    "trading_style": labels.get("trading_style") or "AUTO",
                    "signal_source": labels.get("signal_source") or user.get("signal_source", "RL_DQN"),
                    "model_choice": labels.get("model_choice") or user.get("model_choice", "RL_DQN"),
                    "strike": labels.get("strike"),
                    "manual_sync": False,
                    "bot_recovered": True,
                })
            TradeStore.insert_trade(user_id, record)
            if TradeStore.get_trade_by_id(record["id"]) is None:
                continue
            if inflight:
                inflight_orders.clear(user_id, ap_ticker, side)
            trades.insert(0, record)
            modified = True
            logger.info(f"Synced {'bot (timed-out order)' if inflight else 'manual'} LIVE position from Kalshi for "
                        f"{user.get('username')}: {ap_ticker} {side} x {qty}")
    return modified


def _close_orphaned_open_trades():
    """OPEN trades belonging to users that no longer exist are never visited by the
    per-user loop below, so they would stay OPEN forever. Close them (no P&L)."""
    from backend.database.models import get_db_connection
    from backend.database.trade_store import TradeStore
    try:
        rows = get_db_connection().execute(
            "SELECT user_id, raw_json FROM trades WHERE status = 'OPEN' "
            "AND user_id NOT IN (SELECT id FROM users)"
        ).fetchall()
    except Exception as e:
        logger.warning(f"[SaaSSettler] Orphan check skipped: {e}")
        return
    for uid, raw in rows:
        try:
            t = json.loads(raw) if raw else {}
            if t.get("id"):
                TradeStore.close_if_open(uid, t, {"exit_reason": "ORPHANED_USER_DELETED", "pnl": 0.0,
                                                  "exit_price": t.get("entry_price"), "settled_at": time.time()})
                logger.info(f"[SaaSSettler] Closed orphaned trade {t.get('id')} (user {uid} no longer exists)")
        except Exception as e:
            logger.warning(f"[SaaSSettler] Could not close orphaned trade: {e}")


# One settlement pass at a time inside this process (the fast stop watcher and the
# worker's main loop both call it; the per-user file locks are per-process on Linux).
_settle_lock = threading.Lock()

# No stop-loss in a trade's first seconds, so the entry spread alone can't trigger it.
STOP_LOSS_GRACE_SECONDS = float(os.environ.get("STOP_LOSS_GRACE_SECONDS", "20"))


def settle_saas_trades(blocking: bool = True) -> bool:
    """Run one settlement/exit pass. Returns False if skipped because another pass
    was already running (only possible with blocking=False)."""
    if not _settle_lock.acquire(blocking=blocking):
        return False
    try:
        _settle_saas_trades_pass()
    finally:
        _settle_lock.release()
    return True


def fast_exit_check() -> int:
    """Cheap check (run every ~1.5 s by the worker) for open trades on the current
    market whose stop-loss or take-profit has been reached. If any has, run a full
    settlement pass immediately; that pass re-confirms the trigger with a fresh quote
    and performs the exit with all the usual safeguards.
    Returns the number of triggered trades seen."""
    from backend.database.models import get_db_connection
    rows = get_db_connection().execute(
        "SELECT user_id, raw_json FROM trades WHERE status = 'OPEN'"
    ).fetchall()
    if not rows:
        return 0
    markets: dict = {}
    users = {u["id"]: u for u in (get_all_active_users() or [])}
    now = time.time()
    hits = 0
    for user_id, raw in rows:
        try:
            t = json.loads(raw)
        except (TypeError, ValueError):
            continue
        user = users.get(user_id)
        if not user or t.get("manual_sync"):
            continue
        market = _market_for_ticker(t.get("ticker"), markets)
        if not market or market.get("status") != "active" or t.get("ticker") != market.get("ticker"):
            continue
        side = str(t.get("side", "YES")).lower()
        entry = float(t.get("entry_price") or 0)
        bid = float(market.get(f"{side}_bid") or 0)
        ask = float(market.get(f"{side}_ask") or 0)
        if entry <= 0.01 or bid <= 0:
            continue
        mid = (bid + ask) / 2.0 if ask > 0 else bid
        sl_enabled = bool(user.get("stop_loss_enabled", 1))
        sl = max(0.01, float(user.get("stop_loss_pct", 50.0)) / 100.0)
        tp_enabled = bool(user.get("take_profit_enabled", 1))
        tp = float(user.get("take_profit_pct", 50.0)) / 100.0
        ts_enabled = bool(user.get("trailing_stop_enabled", 0))
        ts_activation = float(user.get("trailing_stop_activation_pct", 35.0)) / 100.0
        ts_dist = float(user.get("trailing_stop_distance_pct", 6.0)) / 100.0
        max_seen = float(t.get("max_seen_bid", entry))
        age = now - _trade_epoch(t.get("timestamp"))

        sl_hit = sl_enabled and (entry - mid) / entry >= sl and age >= STOP_LOSS_GRACE_SECONDS
        tp_hit = tp_enabled and bid > entry and (bid - entry) / entry >= tp
        ts_hit = ts_enabled and ((max_seen - entry) / entry >= ts_activation) and bid <= max(max_seen - ts_dist, max_seen * (1.0 - ts_dist))
        if sl_hit or tp_hit or ts_hit:
            hits += 1
    if hits:
        settle_saas_trades(blocking=False)
    return hits


def _trade_epoch(ts) -> float:
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str) and ts:
        try:
            import datetime
            from zoneinfo import ZoneInfo
            if "ET" in ts:
                return datetime.datetime.strptime(ts, "%Y-%m-%d %I:%M:%S %p ET").replace(
                    tzinfo=ZoneInfo("America/New_York")).timestamp()
            return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError):
            pass
    return 0.0


def _second_entry_mode(user: dict, trade_mode: str, live_kt):
    """The mode a second entry would trade in, or None if it must not happen (audit H2).

    A second entry is a new automated trade, so it respects the user's AI switch. It follows
    the closed trade's own mode - never just the user's current setting - and if the user has
    since switched LIVE<->PAPER it is skipped rather than opened in a mode the original trade
    never used. A LIVE second entry also needs a working Kalshi session (previously a LIVE
    user without one fell through to the PAPER branch and got a paper deduction instead)."""
    if not bool(user.get("ai_enabled", 1)):
        return None
    trade_mode = str(trade_mode or "PAPER").upper()
    if trade_mode != str(user.get("trading_mode", "PAPER")).upper():
        return None
    if trade_mode == "LIVE" and live_kt is None:
        return None
    return trade_mode


def _second_entry_size(user: dict, second_mode: str, ask: float) -> int:
    """Contracts for a second entry. The worst-case fill (ask + the 4c slippage buffer, plus
    the paper latency tax in PAPER) and the Kalshi fee must fit in the user's trade size -
    the same sizing a first entry uses. Previously it sized on the bare ask with no fee."""
    if second_mode == "PAPER":
        risk_amount = float(user.get("paper_trade_size_dollars", 50.0))
        max_cost = min(ask + 0.04 + PAPER_LATENCY_TAX_DOLLARS, 0.99)
    else:
        risk_amount = float(user.get("trade_size_dollars", 5.0))
        max_cost = min(ask + 0.04, 0.99)
    count = int(risk_amount / max(0.01, max_cost))
    while count > 0 and (count * max_cost + kalshi_order_fee(max_cost, count)) > risk_amount:
        count -= 1
    return count


def trigger_saas_take_profit_reentry(
    user_id: int, 
    closed_trade: dict, 
    exit_price: float, 
    is_user_initiated: bool = False,
    live_kt = None
):
    """
    Evaluates and immediately executes a tactical re-entry (2nd or 3rd entry DCA / pullback scalp)
    after a profitable take-profit exit.
    
    Called both from the SaaS settler loop and when a user clicks the Take Profit button on the dashboard.
    """
    from backend.database.models import get_user_by_id
    from backend.database.trade_store import TradeStore, daily_limit_reason
    
    user = get_user_by_id(user_id)
    if not user or not bool(user.get("ai_enabled", 1)):
        return None

    # Re-entry allowed if user enabled multi-entry DCA OR if this was an explicit user Take Profit action
    second_entry_on = bool(user.get("second_entry_enabled", 0))
    if not second_entry_on and not is_user_initiated:
        return None

    # Determine current entry number from closed trade
    curr_entry_num = 1
    if closed_trade.get("is_third_entry") or closed_trade.get("reentry_index") == 3 or "THIRD_ENTRY" in str(closed_trade.get("trading_style", "")).upper():
        curr_entry_num = 3
    elif closed_trade.get("is_second_entry") or closed_trade.get("reentry_index") == 2 or "SECOND_ENTRY" in str(closed_trade.get("trading_style", "")).upper():
        curr_entry_num = 2
    
    next_entry_num = curr_entry_num + 1
    if next_entry_num > 3:
        logger.info(f"[SaaSSettler] Tactical re-entry skipped for user {user.get('username')}: already at max entries ({curr_entry_num}/3)")
        return None

    ticker = closed_trade.get("ticker", "")
    if not ticker:
        return None

    # Verify no active open trade exists for this ticker
    open_trades = TradeStore.get_open_trades(user_id)
    if any(ot.get("ticker") == ticker and str(ot.get("status", "")).upper() == "OPEN" and ot.get("id") != closed_trade.get("id") for ot in open_trades):
        logger.info(f"[SaaSSettler] Tactical re-entry skipped: user {user.get('username')} already has an open trade on {ticker}")
        return None

    # Mode determination
    trade_mode = str(closed_trade.get("mode") or user.get("trading_mode", "PAPER")).upper()
    if trade_mode == "LIVE" and live_kt is None:
        try:
            priv = decrypt_kalshi_key(user.get('kalshi_priv_key_encrypted', ''))
            if priv and user.get('kalshi_key_id'):
                live_kt = KalshiTrader(key_id=user.get('kalshi_key_id'), private_key_pem=priv)
        except Exception as e:
            logger.warning(f"[SaaSSettler] Failed to init live Kalshi trader for user {user_id}: {e}")
            live_kt = None

    second_mode = _second_entry_mode(user, trade_mode, live_kt)
    if not second_mode:
        return None

    # Market quote & time remaining
    market = get_kalshi_15m_market()
    if not market or market.get("status") != "active" or market.get("ticker") != ticker:
        kt_pub = KalshiTrader()
        q = kt_pub.get_market_quote(ticker)
        if q.get("success"):
            market = {
                "ticker": ticker,
                "yes_bid": q.get("yes_bid", 0.0),
                "yes_ask": q.get("yes_ask", 0.0),
                "no_bid": q.get("no_bid", 0.0),
                "no_ask": q.get("no_ask", 0.0),
                "status": "active",
                "close_time": q.get("close_time", "")
            }

    if not market:
        logger.info(f"[SaaSSettler] Tactical re-entry skipped: no active market found for {ticker}")
        return None

    remaining_sec = 900 - (int(time.time()) % 900)
    close_time_str = market.get("close_time", "")
    if close_time_str:
        try:
            import datetime
            ct = datetime.datetime.fromisoformat(close_time_str.replace("Z", "+00:00"))
            remaining_sec = (ct - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
        except Exception:
            pass

    if remaining_sec < 15:
        logger.info(f"[SaaSSettler] Tactical re-entry skipped: {remaining_sec/60.0:.1f}m remaining in candle (< 15s minimum)")
        return None

    reentry_side = str(closed_trade.get("side", "YES")).lower()
    max_ask = float(user.get("second_entry_max_ask", 0.75) or 0.75)
    second_ask = float(market.get(f"{reentry_side}_ask", 0.0))

    if not (0.15 <= second_ask <= max_ask):
        logger.info(f"[SaaSSettler] Tactical re-entry skipped: {reentry_side.upper()} ask ${second_ask:.2f} outside allowed range [0.15, {max_ask:.2f}]")
        return None

    # Tactical pullback verification: ask must be at least 3 cents cheaper than the exit price
    resolved_exit_price = float(exit_price or closed_trade.get("exit_price") or 0.50)
    if second_ask > (resolved_exit_price - 0.03):
        logger.info(f"[SaaSSettler] Tactical re-entry skipped: {reentry_side.upper()} ask ${second_ask:.2f} has not pulled back >= 3Â¢ below exit price ${resolved_exit_price:.2f}")
        return None

    second_count = _second_entry_size(user, second_mode, second_ask)
    if second_count < 1:
        logger.info(f"[SaaSSettler] Tactical re-entry skipped: sized to 0 contracts")
        return None

    if not is_user_initiated and daily_limit_reason(user, second_mode):
        logger.info(f"[SaaSSettler] Tactical re-entry skipped: daily limit reached for user {user.get('username')}")
        return None

    second_id = str(uuid.uuid4())
    can_execute = False
    second_entry_price = second_ask
    reentry_tag = "third_entry" if next_entry_num == 3 else "second_entry"

    if second_mode == "LIVE":
        from backend.database import order_intents
        _se_key = order_intents.account_key_for_user(user_id)
        _se_ticker = f"{ticker}#{reentry_tag}"
        if not order_intents.claim(_se_key, _se_ticker, reentry_side):
            logger.warning(f"[SaaSSettler] Tactical re-entry order_intents claim rejected for {_se_ticker}")
            return None
        order_res = live_kt.place_order(
            ticker=ticker, side=reentry_side, count=second_count,
            limit_price_dollars=second_ask, dry_run=False, slippage_buffer_dollars=0.04
        )
        order_intents.settle_outcome(_se_key, _se_ticker, order_res)
        if order_res.get("success"):
            second_id = order_res.get("client_order_id", second_id)
            second_count = _filled_count(order_res, second_count)
            second_entry_price = float(order_res.get("filled_price", second_ask) or second_ask)
            can_execute = True
        else:
            logger.error(f"[SaaSSettler] Tactical re-entry live order failed: {order_res.get('error')}")
    else:
        sim = paper_kalshi_trader.place_order(
            ticker=ticker, side=reentry_side, count=second_count,
            limit_price_dollars=second_ask, dry_run=True, slippage_buffer_dollars=0.04,
            available_balance=user.get("paper_balance", 500.0),
        )
        if sim.get("success"):
            second_count = _filled_count(sim, second_count)
            second_entry_price = float(sim.get("filled_price", second_ask) or second_ask)
            second_id = sim.get("client_order_id", second_id)
            second_cost = float(sim.get("total_cost", second_count * second_entry_price)) + kalshi_order_fee(second_entry_price, second_count)
            if deduct_user_paper_balance(user_id, second_cost):
                can_execute = True
            else:
                logger.warning(f"[SaaSSettler] Tactical re-entry paper balance deduction failed for user {user_id}")

    if can_execute:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now_est = datetime.now(ZoneInfo("America/New_York")).isoformat()
        style_tag = "THIRD_ENTRY" if next_entry_num == 3 else "SECOND_ENTRY"
        reason_tag = "THIRD_ENTRY_SCALP" if next_entry_num == 3 else "SECOND_ENTRY_SCALP"
        catalyst_desc = f"Tactical pullback re-entry #{next_entry_num} after profitable scalp ({remaining_sec/60.0:.1f}m left)"
        
        new_trade = {
            "id": second_id,
            "ticker": ticker,
            "side": reentry_side.upper(),
            "direction": reentry_side.upper(),
            "prediction_direction": reentry_side.upper(),
            "count": second_count,
            "entry_price": second_entry_price,
            "status": "OPEN",
            "pnl": 0.0,
            "timestamp": now_est,
            "mode": second_mode,
            "reason": reason_tag,
            "is_second_entry": (next_entry_num == 2),
            "is_third_entry": (next_entry_num == 3),
            "is_profit_reentry": True,
            "is_manual": False,
            "reentry_index": next_entry_num,
            "trading_style": style_tag,
            "signal_source": user.get("signal_source", "BLEND"),
            "model_choice": closed_trade.get("model_choice", user.get("model_choice", "RL_DQN")),
            "probability_percent": float(closed_trade.get("probability_percent") or 50.0),
            "catalysts": [catalyst_desc]
        }
        TradeStore.insert_trade(user_id, new_trade)
        
        # Also sync to user's trades_history.json file on disk if it exists
        try:
            hist_path = os.path.join(DATA_DIR, 'users', str(user_id), 'trades_history.json')
            if os.path.exists(hist_path):
                from backend.btc.io_utils import atomic_json_write
                with open(hist_path, 'r', encoding='utf-8') as f:
                    disk_trades = json.load(f)
                disk_trades.append(new_trade)
                atomic_json_write(hist_path, disk_trades, indent=4)
        except Exception as _e:
            logger.warning(f"[SaaSSettler] Could not sync re-entry to disk trades_history.json: {_e}")

        logger.info(f"[SaaSSettler] Tactical Re-entry #{next_entry_num} triggered for user {user.get('username')} on {ticker} ({second_mode}): {second_count} {reentry_side.upper()} @ ${second_entry_price:.2f}")
        return new_trade
    return None


def _recalculate_stop_loss_prediction(ticker: str, market: dict, user: dict, original_side: str):
    """
    On Stop Loss exit, evaluate current market indicators and momentum to determine
    if a re-entry has positive edge, and in which direction.
    
    Returns a dict with:
        - reentry_side: 'yes' or 'no'
        - direction: 'ABOVE' or 'BELOW'
        - prediction_direction: original raw direction from model (e.g. 'ABOVE', 'BELOW')
        - probability_percent: float (e.g. 62.5)
        - is_flipped: bool (True if direction flipped compared to original trade)
        - forecast: dict (raw prediction dict)
    Or None if the setup is PASS/NEUTRAL, low confidence, or evaluation failed.
    """
    try:
        t_upper = str(ticker or "").upper()
        if "ETH" in t_upper:
            asset = "ETH"
        elif "SOL" in t_upper:
            asset = "SOL"
        elif "GOLD" in t_upper:
            asset = "GOLD"
        else:
            asset = "BTC"

        strike = float(market.get("strike_price") or 0.0)

        from backend.engine.multi_asset_fetcher import fetch_asset_candles as fetch_candles
        from backend.btc.indicators import add_all_indicators
        from backend.btc.analyzer.contract_eval import evaluate_next_15m_contract

        df_c = fetch_candles(asset, timeframe="15m", limit=60)
        if df_c is None or df_c.empty:
            logger.warning(f"[SaaSSettler] Could not fetch candles for {asset} during stop-loss recalculation.")
            return None

        df_ind = add_all_indicators(df_c)
        effective_style = user.get("trading_style") or "MOMENTUM_SURFER"
        req_source = user.get("signal_source") or "BLEND"

        forecast = evaluate_next_15m_contract(
            df_ind,
            target_price=strike,
            kalshi_m=market,
            trading_style=effective_style,
            signal_isolation=req_source,
            asset=asset
        )

        pred_dir = str(forecast.get("direction", "")).upper()
        rec = str(forecast.get("recommendation", "")).upper()
        conf = float(forecast.get("probability_percent", 0.0) or 0.0)

        # 1. Gate: Stand down on chop, flat, or no edge
        if pred_dir in ["PASS", "NEUTRAL"] or "PASS" in rec or "NEUTRAL" in rec:
            logger.info(f"[SaaSSettler] Stop loss re-entry aborted for {ticker}: Fresh prediction returned {pred_dir}. Preserving capital.")
            return None

        # 2. Gate: Confidence threshold (default 55.0% for stop-loss re-entries to ensure edge)
        min_conf = float(user.get("min_confidence", 55.0) or 55.0)
        if conf < min_conf:
            logger.info(f"[SaaSSettler] Stop loss re-entry aborted for {ticker}: Confidence {conf:.1f}% is below threshold {min_conf:.1f}%.")
            return None

        # 3. Map direction to yes/no side
        if pred_dir in ["ABOVE", "YES", "UP"]:
            reentry_side = "yes"
            direction = "ABOVE"
        elif pred_dir in ["BELOW", "NO", "DOWN"]:
            reentry_side = "no"
            direction = "BELOW"
        else:
            logger.info(f"[SaaSSettler] Stop loss re-entry aborted for {ticker}: Unrecognized direction '{pred_dir}'.")
            return None

        orig_clean = str(original_side or "").lower()
        is_flipped = (reentry_side != orig_clean)

        if is_flipped:
            logger.info(f"[SaaSSettler] Stop loss re-entry for {ticker} PIVOTED direction: original={orig_clean.upper()} -> new={reentry_side.upper()} (conf: {conf:.1f}%)")
        else:
            logger.info(f"[SaaSSettler] Stop loss re-entry for {ticker} CONFIRMED original direction: {reentry_side.upper()} (conf: {conf:.1f}%)")

        return {
            "reentry_side": reentry_side,
            "direction": direction,
            "prediction_direction": pred_dir,
            "probability_percent": conf,
            "is_flipped": is_flipped,
            "forecast": forecast
        }
    except Exception as e:
        logger.error(f"[SaaSSettler] Exception recalculating stop loss prediction for {ticker}: {e}", exc_info=True)
        return None


def _settle_saas_trades_pass():
    try:
        _close_orphaned_open_trades()
        users = get_all_active_users()
        if not users:
            return
            
        _market_cache: dict = {}  # series -> active market, fetched once per pass
        _quote_cache = {}
        for user in users:
            try:
                user_id = user['id']
                mode = user.get("trading_mode", "PAPER")
                hist_path = os.path.join(DATA_DIR, 'users', str(user_id), 'trades_history.json')
                with get_user_lock(user_id):
                    trades = []
                    if os.path.exists(hist_path):
                        try:
                            with open(hist_path, 'r', encoding='utf-8') as f:
                                trades = json.load(f)
                        except Exception as e:
                            logger.warning(f"Error loading trades from {hist_path}: {e}")
                            trades = []
                
                    # Authoritative SQLite open trades sync
                    from backend.database.trade_store import TradeStore
                    db_open_trades = TradeStore.get_open_trades(user_id)
                    known_ids = {t.get("id") for t in trades if t.get("id")}
                    for ot in db_open_trades:
                        if ot.get("id") not in known_ids:
                            trades.append(ot)
                            known_ids.add(ot.get("id"))
                
                    db_open_ids = {ot.get("id") for ot in db_open_trades}
                    for t in trades:
                        if t.get("status") == "OPEN" and t.get("id") and t.get("id") not in db_open_ids:
                            try:
                                TradeStore.insert_trade(user_id, t)
                            except Exception as _ie:
                                logger.warning(f"TradeStore insert sync error: {_ie}")
                    
                    modified = False
                
                    # Pre-decrypt LIVE credentials once per user (used for both sync and exits)
                    _live_priv = None
                    _live_kt = None
                    if mode == "LIVE" and user.get("kalshi_key_id"):
                        _live_priv = decrypt_kalshi_key(user.get("kalshi_priv_key_encrypted", ""))
                        if _live_priv:
                            _live_kt = KalshiTrader(key_id=user["kalshi_key_id"], private_key_pem=_live_priv)
                
                    # --- KALSHI MANUAL TRADE SYNC ---
                    if _live_kt:
                        try:
                            if _sync_untracked_kalshi_positions(user, user_id, _live_kt, trades):
                                modified = True
                        except Exception as e:
                            logger.error(f"Failed to sync Kalshi positions for {user.get('username')}: {e}")
                    # --- END SYNC ---

                    new_trades_to_add = []
                    for t in trades:
                        if t.get("status") != "OPEN":
                            continue

                        # SQLite is authoritative: if this trade was already closed elsewhere
                        # (manual close endpoints, another process), adopt that state instead of
                        # settling it a second time.
                        _db_row = TradeStore.get_trade_by_id(t.get("id")) if t.get("id") else None
                        if _db_row and str(_db_row.get("status", "OPEN")).upper() != "OPEN":
                            for _k in ("status", "exit_reason", "exit_price", "pnl", "settled_at"):
                                if _k in _db_row:
                                    t[_k] = _db_row[_k]
                            modified = True
                            continue
                        
                        ticker = t.get("ticker")
                        side = t.get("side", "YES").lower()
                        market = _market_for_ticker(ticker, _market_cache)
                        entry = float(t.get("entry_price", 0.0))
                        count = int(t.get("count", 0))
                        if entry <= 0.01 or count <= 0:
                            t["status"] = "CLOSED"
                            t["reason"] = "INVALID_ZERO_PRICE_ENTRY"
                            t["pnl"] = 0.0
                            modified = True
                            continue
                        sl_pct = max(0.01, float(user.get("stop_loss_pct", 50.0)) / 100.0)
                        sl_enabled = bool(user.get("stop_loss_enabled", 1))
                    
                        if not market or market.get("status") != "active" or market.get("ticker") != ticker:
                            from backend.btc.kalshi_trader import kalshi_trader
                            res = kalshi_trader.get_market_result(ticker)
                            ans = res.get("result", "").lower()
                        
                            exit_price = 0.0
                            if ans == "yes":
                                exit_price = 1.0 if side.upper() == "YES" else 0.0
                            elif ans == "no":
                                exit_price = 1.0 if side.upper() == "NO" else 0.0
                            else:
                                # Only fallback to synthetic if it's explicitly a synthetic contract or test ticker
                                if "SYNTH" in ticker.upper() or "TEST" in ticker.upper():
                                    exit_price = 1.0 if float(t.get("probability_percent") or 50.0) > 50 else 0.0
                                else:
                                    continue # Wait for official Kalshi resolution
                                
                            _close = {
                                "exit_reason": "SETTLEMENT",
                                "exit_price": round(exit_price, 4),
                                "pnl": net_pnl(entry, exit_price, count),
                                "settled_at": time.time(),
                            }
                            if not TradeStore.close_if_open(user_id, t, _close):
                                continue  # closed elsewhere; synced from DB next tick
                            t.update(_close)
                            t["status"] = "CLOSED"
                            modified = True
                            logger.info(f"[SaaSSettler] Settled trade {t.get('id')} for {user.get('username')}: {ticker} {side.upper()} -> {ans.upper()} (Exit: ${exit_price:.2f}, PnL: ${t['pnl']:.2f})")
                        
                            trade_mode = str(t.get("mode", mode)).upper()
                            if trade_mode == "PAPER":
                                credit_user_paper_balance(user_id, count * exit_price - kalshi_order_fee(exit_price, count))
                            continue

                        # Positions the bot did not open (synced from the user's Kalshi account) are
                        # tracked for display and settled at expiry, but never auto-sold.
                        if t.get("manual_sync") or t.get("reason") == "MANUAL_KALSHI_SYNC":
                            continue

                        tp_enabled = bool(user.get("take_profit_enabled", 1))
                        tp_pct = float(user.get("take_profit_pct", 50.0)) / 100.0
                        ts_enabled = bool(user.get("trailing_stop_enabled", 0))
                        ts_activation = float(user.get("trailing_stop_activation_pct", 35.0)) / 100.0
                        ts_distance = float(user.get("trailing_stop_distance_pct", 6.0)) / 100.0
                    
                        if market and market.get("ticker") == ticker:
                            curr_bid = market.get(f"{side}_bid", 0.0)
                            curr_ask = market.get(f"{side}_ask", 0.0)
                            if entry > 0:
                                # Use mid-price for stop loss evaluation to avoid getting instantly stopped out by wide bid/ask spreads
                                mid_price = (curr_bid + curr_ask) / 2.0
                                if mid_price <= 0: mid_price = curr_bid
                            
                                # Realizable profit MUST be based on curr_bid: you cannot take profit if bid <= entry!
                                profit_pct = (curr_bid - entry) / entry if curr_bid > 0 else 0.0
                                loss_pct = (entry - mid_price) / entry
                            
                                # But max seen is based on actual bid since that's what you'd sell for
                                max_seen_bid = float(t.get("max_seen_bid", curr_bid))
                                if curr_bid > max_seen_bid:
                                    max_seen_bid = curr_bid
                                    t["max_seen_bid"] = max_seen_bid
                                    modified = True

                                min_seen_bid = float(t.get("min_seen_bid", entry))
                                if curr_bid > 0 and curr_bid < min_seen_bid:
                                    min_seen_bid = curr_bid
                                    t["min_seen_bid"] = min_seen_bid
                                    modified = True
                            
                                max_seen_profit_pct = (max_seen_bid - entry) / entry
                            
                                trigger_exit = False
                                reason = ""
                            
                                if ts_enabled and max_seen_profit_pct >= ts_activation:
                                    trail_threshold = max(max_seen_bid - ts_distance, max_seen_bid * (1.0 - ts_distance))
                                    trail_threshold = max(trail_threshold, entry * 1.02)
                                    if curr_bid <= trail_threshold:
                                        trigger_exit = True
                                        realized_p_pct = (curr_bid - entry) / entry
                                        reason = f"TRAILING_STOP (+{realized_p_pct*100:.1f}%)"
                            
                                if not trigger_exit:
                                    trade_timestamp = t.get("timestamp")
                                    trade_epoch = _trade_epoch(trade_timestamp)

                                    trade_age_seconds = (time.time() - trade_epoch) if trade_epoch > 0 else 999.0
                                    in_grace_period = trade_age_seconds < STOP_LOSS_GRACE_SECONDS

                                    if sl_enabled and loss_pct >= sl_pct and not in_grace_period:
                                        trigger_exit = True
                                        reason = f"STOP_LOSS (-{loss_pct*100:.1f}%)"
                                    elif tp_enabled and profit_pct >= tp_pct and curr_bid > entry:
                                        trigger_exit = True
                                        reason = f"TAKE_PROFIT (+{profit_pct*100:.1f}%)"
                                
                                if trigger_exit:
                                    # The cached market snapshot can be a second or more stale (a LIVE
                                    # "take profit" once fired on a bid that no longer existed and sold at
                                    # the entry price). Re-check the trigger against a fresh quote.
                                    fq = _fresh_quote(ticker, _quote_cache)
                                    if fq is None:
                                        continue
                                    f_bid = float(fq.get(f"{side}_bid") or 0.0)
                                    f_ask = 1.0 - float(fq.get("no_bid" if side == "yes" else "yes_bid") or 0.0)
                                    f_mid = (f_bid + f_ask) / 2.0 if 0.0 < f_ask < 1.0 and f_bid > 0 else f_bid
                                    if reason.startswith("STOP_LOSS"):
                                        f_loss = (entry - f_mid) / entry
                                        still = sl_enabled and f_loss >= sl_pct
                                        reason = f"STOP_LOSS (-{f_loss*100:.1f}%)"
                                    elif reason.startswith("TAKE_PROFIT"):
                                        f_profit = (f_bid - entry) / entry
                                        still = tp_enabled and f_bid > entry and f_profit >= tp_pct
                                        reason = f"TAKE_PROFIT (+{f_profit*100:.1f}%)"
                                    else:  # TRAILING_STOP
                                        still = f_bid > 0 and f_bid <= trail_threshold
                                        reason = f"TRAILING_STOP (+{(f_bid - entry) / entry * 100:.1f}%)"
                                    if not still:
                                        logger.info(f"[SaaSSettler] {reason.split(' ')[0]} for {t.get('id')} not confirmed by fresh quote (bid {f_bid:.2f}); holding.")
                                        continue
                                    curr_bid = f_bid
                                    exit_price = curr_bid
                                    trade_mode = str(t.get("mode", mode)).upper()
                                    if trade_mode == "LIVE":
                                        if not _live_kt:
                                            logger.warning(f"[SaaSSettler] User {user.get('username')} cannot exit LIVE trade {t.get('id')}: no Kalshi session available")
                                            continue
                                    
                                        c_res = _live_kt.close_position(ticker=ticker, purchased_side=side, count=count, dry_run=False)
                                        if not c_res.get("success"):
                                            logger.error(f"[SaaSSettler] LIVE close failed for user {user.get('username')} on {ticker}: {c_res.get('error')}. Position remains OPEN on Kalshi!")
                                            continue
                                    
                                        exit_price = float(c_res.get("exit_price", curr_bid))
                                        live_filled = float(c_res.get("filled_count", count) or count)
                                        count = live_filled
                                        t["count"] = count

                                    _close = {
                                        "exit_reason": reason,
                                        "exit_price": round(exit_price, 4),
                                        "pnl": net_pnl(entry, exit_price, count),
                                        "settled_at": time.time(),
                                        "count": count,
                                    }
                                    if not TradeStore.close_if_open(user_id, t, _close):
                                        continue  # closed elsewhere; never credit twice
                                    t.update(_close)
                                    t["status"] = "CLOSED"
                                    modified = True
                                
                                    if trade_mode == "PAPER":
                                        credit_user_paper_balance(user_id, count * exit_price - kalshi_order_fee(exit_price, count))

                                    # Check tactical re-entry (2nd or 3rd entry) after genuine profitable scalp OR after stop loss if enabled
                                    trade_exit_reason = str(t.get("exit_reason", "") or reason or "").upper()
                                    is_profitable_scalp = ("STOP_LOSS" not in trade_exit_reason) and (exit_price > entry) and (("TAKE_PROFIT" in trade_exit_reason) or ("TRAILING_STOP" in trade_exit_reason))
                                    
                                    is_stop_loss_exit = ("STOP_LOSS" in trade_exit_reason)
                                    reentry_sl_on = bool(user.get("reentry_after_stop_loss", 0))

                                    if is_profitable_scalp or (is_stop_loss_exit and reentry_sl_on):
                                        # Clear interval lockout and order_intents so bot can re-enter
                                        try:
                                            from backend.btc.auto_executor.shared import _user_last_traded_cache, _user_last_traded_lock
                                            with _user_last_traded_lock:
                                                for k in [k for k in _user_last_traded_cache if k[0] == user_id]:
                                                    _user_last_traded_cache.pop(k, None)
                                            from backend.database import order_intents
                                            _acc_k = order_intents.account_key_for_user(user_id)
                                            order_intents.release(_acc_k, ticker)
                                        except Exception as _lk_err:
                                            logger.warning(f"[SaaSSettler] Lockout release warning: {_lk_err}")
                                            
                                    second_entry_on = bool(user.get("second_entry_enabled", 0))

                                    allow_reentry = (is_profitable_scalp and second_entry_on) or (is_stop_loss_exit and reentry_sl_on)

                                    # Current trade's entry index:
                                    # 1: initial trade
                                    # 2: second entry
                                    # 3: third entry
                                    curr_entry_num = 1
                                    if t.get("is_third_entry") or t.get("reentry_index") == 3 or "THIRD_ENTRY" in str(t.get("trading_style", "")).upper():
                                        curr_entry_num = 3
                                    elif t.get("is_second_entry") or t.get("reentry_index") == 2 or "SECOND_ENTRY" in str(t.get("trading_style", "")).upper():
                                        curr_entry_num = 2

                                    next_entry_num = curr_entry_num + 1
                                    can_reenter_count = (next_entry_num <= 3)

                                    # No other open trade on this ticker
                                    no_open_on_ticker = not any(
                                        ot.get("ticker") == ticker and str(ot.get("status", "")).upper() == "OPEN" and ot.get("id") != t.get("id")
                                        for ot in (trades + new_trades_to_add)
                                    )
                                    # Ensure we have not already placed or queued this next entry level for this ticker
                                    already_has_next_entry = any(
                                        ot.get("ticker") == ticker and (
                                            (next_entry_num == 2 and (ot.get("is_second_entry") or ot.get("reentry_index") == 2)) or
                                            (next_entry_num == 3 and (ot.get("is_third_entry") or ot.get("reentry_index") == 3))
                                        )
                                        for ot in (trades + new_trades_to_add)
                                    )
                                    second_mode = _second_entry_mode(user, trade_mode, _live_kt)

                                    if allow_reentry and can_reenter_count and no_open_on_ticker and not already_has_next_entry and second_mode:
                                        remaining_sec = 900 - (int(time.time()) % 900)
                                        close_time_str = market.get("close_time", "")
                                        if close_time_str:
                                            try:
                                                import datetime
                                                ct = datetime.datetime.fromisoformat(close_time_str.replace("Z", "+00:00"))
                                                remaining_sec = (ct - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
                                            except (ValueError, TypeError) as e:
                                                logger.warning(f"[SaaSSettler] Error parsing close_time {close_time_str}: {e}")
                                            
                                        if remaining_sec < 15:
                                            continue

                                        reentry_side = side
                                        reentry_direction = side.upper()
                                        reentry_pred_direction = side.upper()
                                        reentry_conf = float(t.get("probability_percent") or 50.0)
                                        is_flipped = False

                                        if is_stop_loss_exit:
                                            # Recalculate AI prediction dynamically on stop loss!
                                            recalc = _recalculate_stop_loss_prediction(ticker, market, user, side)
                                            if not recalc:
                                                continue  # Stand down: PASS, low confidence, or error
                                            reentry_side = recalc["reentry_side"]
                                            reentry_direction = recalc["direction"]
                                            reentry_pred_direction = recalc["prediction_direction"]
                                            reentry_conf = recalc["probability_percent"]
                                            is_flipped = recalc["is_flipped"]

                                        max_ask = float(user.get("second_entry_max_ask", 0.75))
                                        second_ask = float(market.get(f"{reentry_side}_ask", 0.0))
                                    
                                        if 0.15 <= second_ask <= max_ask:
                                            second_count = _second_entry_size(user, second_mode, second_ask)
                                            if second_count < 1:
                                                continue
                                            from backend.database.trade_store import \
                                                daily_limit_reason
                                            if daily_limit_reason(user, second_mode):
                                                continue
                                            second_id = str(uuid.uuid4())
                                            can_execute = False
                                        
                                            second_entry_price = second_ask
                                            reentry_tag = "third_entry" if next_entry_num == 3 else "second_entry"
                                            if second_mode == "LIVE":
                                                from backend.database import \
                                                    order_intents
                                                _se_key = order_intents.account_key_for_user(user_id)
                                                _se_ticker = f"{ticker}#{reentry_tag}"
                                                if not order_intents.claim(_se_key, _se_ticker, reentry_side):
                                                    continue
                                                order_res = _live_kt.place_order(ticker=ticker, side=reentry_side, count=second_count, limit_price_dollars=second_ask, dry_run=False, slippage_buffer_dollars=0.04)
                                                order_intents.settle_outcome(_se_key, _se_ticker, order_res)
                                                if order_res.get("success"):
                                                    second_id = order_res.get("client_order_id", second_id)
                                                    second_count = _filled_count(order_res, second_count)
                                                    second_entry_price = float(order_res.get("filled_price", second_ask) or second_ask)
                                                    can_execute = True
                                            else:
                                                sim = paper_kalshi_trader.place_order(
                                                    ticker=ticker, side=reentry_side, count=second_count,
                                                    limit_price_dollars=second_ask, dry_run=True, slippage_buffer_dollars=0.04,
                                                    available_balance=user.get("paper_balance", 500.0),
                                                )
                                                if sim.get("success"):
                                                    second_count = _filled_count(sim, second_count)
                                                    second_entry_price = float(sim.get("filled_price", second_ask) or second_ask)
                                                    second_id = sim.get("client_order_id", second_id)
                                                    second_cost = float(sim.get("total_cost", second_count * second_entry_price)) + kalshi_order_fee(second_entry_price, second_count)
                                                    if deduct_user_paper_balance(user_id, second_cost):
                                                        can_execute = True
                                                
                                            if can_execute:
                                                from datetime import datetime
                                                from zoneinfo import ZoneInfo
                                                now_est = datetime.now(ZoneInfo("America/New_York")).isoformat()
                                                style_tag = "THIRD_ENTRY" if next_entry_num == 3 else "SECOND_ENTRY"
                                                if is_stop_loss_exit:
                                                    reason_tag = f"STOP_LOSS_REENTRY_{next_entry_num}"
                                                    if is_flipped:
                                                        catalyst_desc = f"Pivoted re-entry #{next_entry_num} after stop loss flipped to {reentry_side.upper()} (conf: {reentry_conf:.1f}%, {remaining_sec/60.0:.1f}m left)"
                                                    else:
                                                        catalyst_desc = f"Dip re-entry #{next_entry_num} after stop loss confirmed {reentry_side.upper()} (conf: {reentry_conf:.1f}%, {remaining_sec/60.0:.1f}m left)"
                                                else:
                                                    reason_tag = "THIRD_ENTRY_SCALP" if next_entry_num == 3 else "SECOND_ENTRY_SCALP"
                                                    catalyst_desc = f"Tactical pullback re-entry #{next_entry_num} after profitable scalp ({remaining_sec/60.0:.1f}m left)"
                                                rem_min = remaining_sec / 60.0
                                                new_trades_to_add.append({
                                                    "id": second_id,
                                                    "ticker": ticker,
                                                    "side": reentry_side.upper(),
                                                    "direction": reentry_direction,
                                                    "prediction_direction": reentry_pred_direction,
                                                    "count": second_count,
                                                    "entry_price": second_entry_price,
                                                    "status": "OPEN",
                                                    "pnl": 0.0,
                                                    "timestamp": now_est,
                                                    "mode": second_mode,
                                                    "reason": reason_tag,
                                                    "is_second_entry": (next_entry_num == 2),
                                                    "is_third_entry": (next_entry_num == 3),
                                                    "is_stop_loss_reentry": is_stop_loss_exit,
                                                    "reentry_flipped": is_flipped if is_stop_loss_exit else False,
                                                    "reentry_index": next_entry_num,
                                                    "trading_style": style_tag,
                                                    "signal_source": user.get("signal_source", "BLEND"),
                                                    "model_choice": t.get("model_choice", user.get("model_choice", "RL_DQN")),
                                                    "probability_percent": reentry_conf,
                                                    "catalysts": [catalyst_desc]
                                                })
                                                modified = True
                                                if is_stop_loss_exit:
                                                    pivot_label = " (Pivoted)" if is_flipped else " (Dip)"
                                                    log_action = f"Stop-Loss{pivot_label} Re-entry #{next_entry_num}"
                                                else:
                                                    log_action = f"Re-entry #{next_entry_num}"
                                                logger.info(f"[SaaSSettler] {log_action} triggered for user {user.get('username')} on {ticker} ({second_mode}): {second_count} {reentry_side.upper()} @ ${second_entry_price:.2f}")

                    if new_trades_to_add:
                        trades.extend(new_trades_to_add)
                        try:
                            from backend.database.trade_store import TradeStore
                            for t in new_trades_to_add:
                                TradeStore.insert_trade(user_id, t)
                        except Exception as e:
                            logger.error(f"[SaaSSettler] Error inserting new second entries to TradeStore: {e}")

                    if modified:
                        try:
                            os.makedirs(os.path.dirname(hist_path), exist_ok=True)
                            from backend.btc.io_utils import atomic_json_write
                            atomic_json_write(hist_path, trades, indent=4)
                        except Exception as fe:
                            logger.error(f"[SaaSSettler] Error saving {hist_path}: {fe}")
                    
                        try:
                            from backend.database.trade_store import TradeStore
                            for t in trades:
                                if not t.get('id'):
                                    continue
                                # Never let this (possibly stale) copy re-open a trade closed elsewhere
                                TradeStore.update_trade(t['id'], t, only_if_open=(str(t.get('status', 'OPEN')).upper() == 'OPEN'))
                        except Exception as e:
                            logger.error(f"[SaaSSettler] Error updating trades in TradeStore: {e}")
                        
            except Exception as e:
                # One user's failure must not stop settlement for everyone else
                logger.error(f"[SaaSSettler] Error settling user {user.get('username', user.get('id'))}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"[SaaSSettler] Error: {e}")

def process_auto_force_trades():
    """
    Deprecated / Legacy fallback.
    Auto-force trade execution is now unified and centrally handled by 
    saas_broadcaster.evaluate_and_execute_saas_users() across BTC, ETH, and GOLD
    with in-memory interval caching and strict risk caps to prevent duplicate orders.
    """
    return


# â”€â”€ P3: Trades archival â€” keeps trades_history.json lean â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_last_archive_run: float = 0.0
_ARCHIVE_INTERVAL = 86400.0  # run at most once every 24 hours

def archive_old_trades(max_age_days: int = 30) -> None:
    """
    Move SETTLED/CLOSED trades older than `max_age_days` from each user's
    trades_history.json into a sidecar trades_history_archive.json.
    Runs at most once per 24 hours regardless of how often it is called.
    """
    global _last_archive_run
    now = time.time()
    if now - _last_archive_run < _ARCHIVE_INTERVAL:
        return
    _last_archive_run = now

    users_dir = os.path.join(DATA_DIR, "users")
    if not os.path.isdir(users_dir):
        return

    cutoff = now - (max_age_days * 86400)

    for uid_dir in os.listdir(users_dir):
        hist_path = os.path.join(users_dir, uid_dir, "trades_history.json")
        if not os.path.exists(hist_path):
            continue
        archive_path = os.path.join(users_dir, uid_dir, "trades_history_archive.json")
        try:
            with get_user_lock(uid_dir):
                with open(hist_path, "r") as f:
                    trades = json.load(f)

                keep, to_archive = [], []
                for t in trades:
                    if t.get("status") == "OPEN":
                        keep.append(t)
                        continue
                    # Parse timestamp to decide age
                    try:
                        ts_str = t.get("timestamp", "")
                        import datetime as _dt
                        ts_clean = ts_str[:19].replace('T', ' ')
                        ts = _dt.datetime.strptime(ts_clean, "%Y-%m-%d %H:%M:%S")
                        trade_ts = ts.timestamp()
                    except (ValueError, TypeError) as e:
                        logger.warning(f"[Archive] Error parsing timestamp {ts_str}: {e}")
                        keep.append(t)
                        continue
                    if trade_ts < cutoff:
                        to_archive.append(t)
                    else:
                        keep.append(t)

                if not to_archive:
                    continue

                # Load existing archive and append
                existing_archive = []
                if os.path.exists(archive_path):
                    try:
                        with open(archive_path, "r") as f:
                            existing_archive = json.load(f)
                    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
                        logger.warning(f"[Archive] Error loading {archive_path}: {e}")
                existing_archive.extend(to_archive)

                with open(archive_path, "w") as f:
                    json.dump(existing_archive, f, indent=2)
                with open(hist_path, "w") as f:
                    json.dump(keep, f, indent=4)

                logger.info(f"[Archive] User {uid_dir}: archived {len(to_archive)} old trades, {len(keep)} retained.")
        except Exception as e:
            logger.warning(f"[Archive] Failed for user {uid_dir}: {e}")



