"""
Shared LIVE-order lifecycle helpers for the Investments universe.

- submit_exit(): sends the real opposite-side broker order for an open trade and only
  closes it locally once the broker confirms a fill (otherwise stores metadata.pending_close).
- reconcile_live_trades(): read-only polling of broker order state for local LIVE trades
  (pending entries -> fill price / CANCELLED / REJECTED; pending exits -> CLOSED).
- side-aware P&L helpers.

Trades stay status OPEN in the DB while pending; broker state lives in metadata:
  pending_fill (bool), broker_state, pending_close {order_id, state, reason, submitted_at}.
"""

import datetime
import json
import logging
import time
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from backend.database.trade_store import TradeStore

logger = logging.getLogger(__name__)
NY_TZ = ZoneInfo("America/New_York")

FILLED_STATE = "filled"
DEAD_STATES = ("cancelled", "canceled", "rejected", "failed", "voided", "expired")


def parse_meta(trade: Dict[str, Any]) -> Dict[str, Any]:
    meta = trade.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    return dict(meta) if isinstance(meta, dict) else {}


def is_live(trade: Dict[str, Any]) -> bool:
    return str(trade.get("mode") or "PAPER").upper() == "LIVE"


def trade_direction(trade: Dict[str, Any]) -> int:
    """+1 for long (BUY-opened) positions, -1 for short (SELL-opened)."""
    return -1 if str(trade.get("side") or "BUY").upper() == "SELL" else 1


def exit_action(trade: Dict[str, Any]) -> str:
    """Closing side: sell to close a long, buy to close/cover a short."""
    return "BUY" if trade_direction(trade) < 0 else "SELL"


def compute_pnl(trade: Dict[str, Any], exit_price: float, vehicle: Optional[str] = None) -> float:
    meta = parse_meta(trade)
    veh = (vehicle or meta.get("vehicle") or "STOCK").upper()
    mult = 100.0 if veh == "OPTION" else 1.0
    entry = float(trade.get("entry_price") or 0.0)
    count = float(trade.get("count") or 0.0)
    return round((float(exit_price) - entry) * count * mult * trade_direction(trade), 2)


def settle_paper_balance(user_id: int, trade: Dict[str, Any], exit_price: float) -> None:
    """Paper settlement. Long buys debited cost at entry -> credit exit proceeds.
    Shorts (SELL-opened) debited nothing at entry -> apply only the realized P&L."""
    from backend.database.models import credit_user_investments_paper_balance, deduct_user_investments_paper_balance
    meta = parse_meta(trade)
    mult = 100.0 if str(meta.get("vehicle") or "STOCK").upper() == "OPTION" else 1.0
    count = float(trade.get("count") or 0.0)
    if trade_direction(trade) > 0:
        credit_user_investments_paper_balance(user_id, round(float(exit_price) * count * mult, 2))
    else:
        pnl = compute_pnl(trade, exit_price)
        if pnl >= 0:
            credit_user_investments_paper_balance(user_id, pnl)
        else:
            deduct_user_investments_paper_balance(user_id, -pnl)


def update_meta(trade: Dict[str, Any], changes: Dict[str, Any], top: Optional[Dict[str, Any]] = None) -> bool:
    """Merge metadata changes (and optional top-level fields) into an OPEN trade row."""
    meta = parse_meta(trade)
    meta.update(changes)
    upd = dict(top or {})
    upd["metadata"] = json.dumps(meta)
    ok = TradeStore.update_trade(trade["id"], upd, only_if_open=True)
    if ok:
        trade["metadata"] = upd["metadata"]
        for k, v in (top or {}).items():
            trade[k] = v
    return ok


def finalize_close(user_id: int, trade: Dict[str, Any], exit_price: float, reason: str,
                   extra_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    pnl = compute_pnl(trade, exit_price)
    meta = parse_meta(trade)
    meta.pop("pending_close", None)
    meta.update(extra_meta or {})
    closed = TradeStore.close_if_open(user_id, trade, {
        "status": "CLOSED",
        "exit_price": float(exit_price),
        "pnl": pnl,
        "pnl_dollars": pnl,
        "exit_reason": reason,
        "settled_at": time.time(),
        "closed_at": datetime.datetime.now(NY_TZ).isoformat(),
        "metadata": json.dumps(meta),
    })
    return {"status": "CLOSED", "closed": closed, "exit_price": float(exit_price), "pnl": pnl, "exit_reason": reason}


def _f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def submit_exit(user_id: int, trade: Dict[str, Any], client: Any, reason: str) -> Dict[str, Any]:
    """Send the real LIVE exit order. Returns dict with status CLOSED | PENDING_CLOSE | ERROR."""
    meta = parse_meta(trade)
    pc = meta.get("pending_close") or {}
    if pc.get("order_id") and str(pc.get("state") or "").lower() not in DEAD_STATES:
        return {"status": "PENDING_CLOSE", "order_id": pc.get("order_id"), "broker_state": pc.get("state"),
                "message": "An exit order is already working for this trade."}
    if meta.get("pending_fill"):
        return {"status": "ERROR", "error": "Entry order has not filled yet - cancel the order instead of closing."}

    vehicle = str(meta.get("vehicle") or "STOCK").upper()
    symbol = meta.get("symbol") or str(trade.get("ticker") or "").split("_")[0]
    count = float(trade.get("count") or 0.0)
    if count <= 0:
        return {"status": "ERROR", "error": "Trade has no filled quantity to close."}
    action = exit_action(trade)
    try:
        if vehicle == "OPTION":
            kwargs = {}
            from backend.investments.robinhood_client import RobinhoodMCPAdapter
            if isinstance(client, RobinhoodMCPAdapter):
                kwargs["position_effect"] = "close"
            res = client.place_option_order(
                symbol=symbol,
                strike=float(meta.get("strike") or 0.0),
                expiration=str(meta.get("expiration") or ""),
                option_type=str(meta.get("option_type") or "CALL"),
                action=action,
                contracts=int(round(count)),
                **kwargs
            )
        else:
            res = client.place_stock_order(symbol=symbol, action=action, shares=count)
    except Exception as e:
        logger.error(f"[LiveOps] exit order exception user #{user_id} {trade.get('id')}: {e}")
        res = {"success": False, "error": f"Exit order error: {e}"}

    if not res or not res.get("success"):
        err = (res or {}).get("error") or "Exit order rejected by broker."
        update_meta(trade, {"last_exit_error": str(err)[:400], "last_exit_error_at": time.time()})
        return {"status": "ERROR", "error": err}

    state = str(res.get("state") or res.get("status") or "").lower()
    order_id = res.get("order_id")
    fill_px = res.get("filled_price")
    if state == FILLED_STATE and fill_px:
        out = finalize_close(user_id, trade, float(fill_px), reason, {"exit_order_id": order_id})
        out["order_id"] = order_id
        return out

    update_meta(trade, {"pending_close": {
        "order_id": order_id, "state": state or "submitted", "reason": reason,
        "action": action, "submitted_at": time.time()
    }, "last_exit_error": None})
    return {"status": "PENDING_CLOSE", "order_id": order_id, "broker_state": state or "submitted"}


def reconcile_live_trades(user_id: int, client: Any, trades: Optional[List[Dict[str, Any]]] = None) -> Dict[str, int]:
    """Read-only reconciliation of pending LIVE entries/exits against broker order state."""
    stats = {"checked": 0, "filled": 0, "cancelled": 0, "closed": 0, "exit_failed": 0}
    if not hasattr(client, "get_order"):
        return stats
    if trades is None:
        trades = [t for t in TradeStore.get_open_trades(user_id)
                  if str(t.get("asset") or "").upper() == "INVESTMENTS"]
    for t in trades:
        if not is_live(t):
            continue
        meta = parse_meta(t)
        vehicle = str(meta.get("vehicle") or "STOCK").upper()
        try:
            if meta.get("pending_fill"):
                stats["checked"] += 1
                o = client.get_order(t["id"], vehicle=vehicle)
                if not o:
                    # Check staleness: if order has been pending fill for over 48 hours without being found at broker, mark stale/cancelled
                    opened_ts = _f(t.get("timestamp") or 0.0)
                    if opened_ts > 0 and (time.time() - opened_ts) > 172800:
                        meta.update({"pending_fill": False, "broker_state": "stale_not_found"})
                        TradeStore.update_trade(t["id"], {
                            "status": "CANCELLED",
                            "exit_price": t.get("entry_price"), "pnl": 0.0, "pnl_dollars": 0.0,
                            "exit_reason": "STALE_ORDER_EXPIRED", "settled_at": time.time(),
                            "metadata": json.dumps(meta)
                        }, only_if_open=True)
                        stats["cancelled"] += 1
                    continue
                state = str(o.get("state") or "").lower()
                cum = _f(o.get("cumulative_quantity") or o.get("processed_quantity"))
                avg = _f(o.get("average_price") or o.get("processed_premium_per_contract"))
                if state == FILLED_STATE and avg > 0:
                    update_meta(t, {"pending_fill": False, "broker_state": state, "filled_at": time.time()},
                                {"entry_price": avg, "count": cum or float(t.get("count") or 0.0)})
                    stats["filled"] += 1
                elif state in DEAD_STATES:
                    if cum > 0 and avg > 0:
                        # partially filled then cancelled: keep the filled part as an open position
                        update_meta(t, {"pending_fill": False, "broker_state": state, "partial_fill": True},
                                    {"entry_price": avg, "count": cum})
                        stats["filled"] += 1
                    else:
                        meta.update({"pending_fill": False, "broker_state": state})
                        TradeStore.update_trade(t["id"], {
                            "status": "REJECTED" if state in ("rejected", "failed") else "CANCELLED",
                            "exit_price": t.get("entry_price"), "pnl": 0.0, "pnl_dollars": 0.0,
                            "exit_reason": f"BROKER_{state.upper()}", "settled_at": time.time(),
                            "metadata": json.dumps(meta)
                        }, only_if_open=True)
                        stats["cancelled"] += 1
                elif state and state != meta.get("broker_state"):
                    update_meta(t, {"broker_state": state})
            pc = meta.get("pending_close") or {}
            if pc.get("order_id") and str(pc.get("state") or "").lower() not in DEAD_STATES:
                stats["checked"] += 1
                o = client.get_order(pc["order_id"], vehicle=vehicle)
                if not o:
                    continue
                state = str(o.get("state") or "").lower()
                avg = _f(o.get("average_price") or o.get("processed_premium_per_contract"))
                if state == FILLED_STATE and avg > 0:
                    finalize_close(user_id, t, avg, pc.get("reason") or "MANUAL_CLOSE", {"exit_order_id": pc["order_id"]})
                    stats["closed"] += 1
                elif state in DEAD_STATES:
                    pc = dict(pc, state=state)
                    update_meta(t, {"pending_close": pc,
                                    "last_exit_error": f"Exit order {pc['order_id']} {state} at broker; position still open."})
                    stats["exit_failed"] += 1
                elif state and state != pc.get("state"):
                    update_meta(t, {"pending_close": dict(pc, state=state)})
        except Exception as e:
            logger.warning(f"[LiveOps] reconcile error user #{user_id} trade {t.get('id')}: {e}")
    return stats



def sync_broker_positions(user_id: int, client: Any) -> Dict[str, Any]:
    """
    Two-way position reconciler:
    Fetches real active stock and options positions directly from Robinhood (MCP)
    and synchronizes them into local TradeStore if placed via Robinhood mobile/web.
    """
    stats = {"synced_stocks": 0, "synced_options": 0, "errors": []}
    if not hasattr(client, "call_tool") or not hasattr(client, "_agentic_account_number"):
        return stats

    acct = client._agentic_account_number()
    if not acct:
        return stats

    try:
        eq_res = client.call_tool("get_equity_positions", {"account_number": acct})
        if eq_res.get("success"):
            d = eq_res.get("data")
            while isinstance(d, dict) and isinstance(d.get("data"), dict):
                d = d["data"]
            positions = (d or {}).get("positions") or []
            open_trades = [t for t in TradeStore.get_open_trades(user_id) if is_live(t)]
            open_syms = set()
            for t in open_trades:
                m = parse_meta(t)
                s = m.get("symbol") or str(t.get("ticker") or "").split("_")[0]
                if s:
                    open_syms.add(s.upper())

            for p in positions:
                sym = str(p.get("symbol") or "").upper()
                qty = _f(p.get("shares_available_for_sells") or p.get("quantity"))
                avg_px = _f(p.get("average_buy_price"))
                if sym and qty > 0 and sym not in open_syms:
                    now_ny = datetime.datetime.now(NY_TZ).isoformat()
                    trade_id = f"RH-SYNC-{sym}-{int(time.time()*1000)}"
                    trade_rec = {
                        "id": trade_id,
                        "user_id": user_id,
                        "ticker": sym,
                        "side": "BUY",
                        "entry_price": avg_px,
                        "count": qty,
                        "status": "OPEN",
                        "pnl": 0.0,
                        "mode": "LIVE",
                        "reason": f"ROBINHOOD_APP_SYNC ({qty} sh @ ${avg_px:.2f})",
                        "trading_style": "MANUAL",
                        "signal_source": "ROBINHOOD_APP",
                        "timestamp": now_ny,
                        "asset": "INVESTMENTS",
                        "metadata": json.dumps({
                            "universe": "INVESTMENTS",
                            "vehicle": "STOCK",
                            "symbol": sym,
                            "shares": qty,
                            "broker": "ROBINHOOD_MCP",
                            "broker_state": "filled",
                            "account_number": acct,
                            "synced_from_broker": True
                        })
                    }
                    TradeStore.insert_trade(user_id, trade_rec)
                    stats["synced_stocks"] += 1
                    open_syms.add(sym)

        # Sync Active Options Positions from Robinhood MCP
        opt_res = client.call_tool("get_option_positions", {"account_number": acct, "nonzero": True})
        if opt_res.get("success"):
            od = opt_res.get("data")
            while isinstance(od, dict) and isinstance(od.get("data"), dict):
                od = od["data"]
            opt_positions = (od or {}).get("positions") or []
            open_opt_ids = set()
            for t in open_trades:
                m = parse_meta(t)
                oid = m.get("option_id") or m.get("contract_id") or t.get("ticker")
                if oid:
                    open_opt_ids.add(str(oid))

            for op in opt_positions:
                op_id = op.get("option_id") or op.get("id")
                qty = _f(op.get("quantity"))
                avg_px = _f(op.get("average_price"))
                chain_sym = str(op.get("chain_symbol") or "").upper()
                exp_date = str(op.get("expiration_date") or "")
                op_type = str(op.get("type") or "call").upper()
                if op_id and qty > 0 and str(op_id) not in open_opt_ids:
                    now_ny = datetime.datetime.now(NY_TZ).isoformat()
                    trade_id = f"RH-OPT-SYNC-{chain_sym}-{int(time.time()*1000)}"
                    ticker_label = f"{chain_sym}_{exp_date}_{op_type}"
                    trade_rec = {
                        "id": trade_id,
                        "user_id": user_id,
                        "ticker": ticker_label,
                        "side": "BUY",
                        "entry_price": avg_px,
                        "count": qty,
                        "status": "OPEN",
                        "pnl": 0.0,
                        "mode": "LIVE",
                        "reason": f"ROBINHOOD_APP_OPT_SYNC ({qty} {chain_sym} {op_type} @ ${avg_px:.2f})",
                        "trading_style": "MANUAL",
                        "signal_source": "ROBINHOOD_APP",
                        "timestamp": now_ny,
                        "asset": "INVESTMENTS",
                        "metadata": json.dumps({
                            "universe": "INVESTMENTS",
                            "vehicle": "OPTION",
                            "symbol": chain_sym,
                            "option_id": str(op_id),
                            "contracts": qty,
                            "expiration": exp_date,
                            "option_type": op_type,
                            "broker": "ROBINHOOD_MCP",
                            "broker_state": "filled",
                            "account_number": acct,
                            "synced_from_broker": True
                        })
                    }
                    TradeStore.insert_trade(user_id, trade_rec)
                    stats["synced_options"] += 1
                    open_opt_ids.add(str(op_id))
    except Exception as e:
        stats["errors"].append(str(e))

    return stats
