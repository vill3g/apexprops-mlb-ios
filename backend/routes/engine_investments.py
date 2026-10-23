"""
Investments Universe API Endpoints
Provides routes for:
- /api/engine/investments/scanner: Live multi-factor scanner + market breadth
- /api/engine/investments/portfolio: Real-time Robinhood buying power, positions, and day-trade status
- /api/engine/investments/trade: 1-click manual stock / option order execution
- /api/engine/investments/close: Close / take-profit individual investment position
- /api/engine/investments/close-all: Emergency flatten all investment positions
- /api/engine/investments/config: Fetch and update Investments universe settings
"""

import base64
import datetime
import hashlib
import json
import logging
import secrets
import threading
import time
import urllib.parse
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional, Any
import requests
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from backend.auth.routes import get_current_user
from backend.auth.security import encrypt_kalshi_key, decode_jwt_token
from backend.database.models import (
    get_user_by_id,
    update_user_investments_config,
    save_user_robinhood_credentials,
    credit_user_investments_paper_balance,
    deduct_user_investments_paper_balance
)
from backend.database.trade_store import TradeStore
from backend.investments.robinhood_client import (
    RobinhoodClientFactory,
    RobinhoodMarketSession,
    RobinhoodMCPAdapter,
    DEFAULT_ROBINHOOD_MCP_URL,
    ROBINHOOD_MCP_STANDARD_TOOLS,
    get_live_stock_quote,
    get_decision_quote,
    quote_is_usable,
    black_scholes_price
)
from backend.investments.risk_engine import RiskEngine
from backend.investments.performance_tracker import PerformanceTracker
from backend.investments.live_ops import (
    reconcile_live_trades,
    sync_broker_positions,
    settle_paper_balance,
    submit_exit,
    compute_pnl,
    parse_meta,
    update_meta
)
from backend.investments.intraday_scanner import IntradayStockScanner
from backend.investments.options_selector import OptionsContractSelector
from backend.investments.agentic_desk import AgenticInvestmentsDesk
from backend.investments.market_screener import DynamicMarketScreener

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/engine/investments", tags=["investments"])
_scanner = IntradayStockScanner()
_desk = AgenticInvestmentsDesk()


class ManualStockOrderRequest(BaseModel):
    symbol: str
    action: str = "BUY"  # BUY or SELL
    shares: Optional[float] = 0.0
    notional_dollars: Optional[float] = None
    order_type: str = "MARKET"
    limit_price: Optional[float] = None
    tp_pct: Optional[float] = None
    sl_pct: Optional[float] = None


class ManualOptionOrderRequest(BaseModel):
    symbol: str
    action: str = "BUY"  # BUY or SELL
    option_type: str = "CALL"  # CALL or PUT
    strike: float
    expiration: str
    contracts: int = 1
    order_type: str = "MARKET"
    limit_price: Optional[float] = None
    tp_pct: Optional[float] = None
    sl_pct: Optional[float] = None


class InvestmentsSettingsRequest(BaseModel):
    investments_paper_balance: Optional[float] = None
    investments_trade_size_dollars: Optional[float] = None
    investments_paper_trade_size_dollars: Optional[float] = None
    investments_asset_classes: Optional[str] = None
    investments_screener_mode: Optional[str] = None
    investments_watchlist: Optional[str] = None
    investments_strategy: Optional[str] = None
    investments_min_confidence: Optional[float] = None
    investments_min_rvol: Optional[float] = None
    investments_max_daily_trades: Optional[int] = None
    investments_max_open_positions: Optional[int] = None
    investments_max_daily_risk: Optional[float] = None
    investments_stock_tp_pct: Optional[float] = None
    investments_stock_sl_pct: Optional[float] = None
    investments_option_tp_pct: Optional[float] = None
    investments_option_sl_pct: Optional[float] = None
    investments_trailing_stop_enabled: Optional[bool] = None
    investments_trailing_stop_pct: Optional[float] = None
    investments_eod_auto_flatten: Optional[bool] = None
    investments_extended_hours: Optional[bool] = None
    investments_allow_fractional: Optional[bool] = None
    investments_options_delta_target: Optional[float] = None
    investments_options_dte_window: Optional[str] = None
    investments_options_max_spread_pct: Optional[float] = None
    investments_options_min_oi: Optional[int] = None
    investments_use_kelly: Optional[bool] = None
    investments_live_autotrade_enabled: Optional[bool] = None
    investments_live_max_dollars_per_day: Optional[float] = None
    investments_risk_per_trade_pct: Optional[float] = None
    investments_max_exposure_pct: Optional[float] = None
    investments_max_consecutive_losses: Optional[int] = None
    investments_cooldown_minutes: Optional[int] = None
    rh_auth_mode: Optional[str] = None
    rh_account_type: Optional[str] = None
    rh_mcp_url: Optional[str] = None


class MCPTestRequest(BaseModel):
    mcp_url: Optional[str] = None
    mcp_token: Optional[str] = None


class MCPOAuthStartRequest(BaseModel):
    origin: Optional[str] = None
    redirect_mode: Optional[str] = "CURSOR_SCHEME"  # "CURSOR_SCHEME", "CLAUDE_WEB", or "LOCAL_CALLBACK"


class MCPOAuthExchangeRequest(BaseModel):
    callback_url_or_code: str
    state: Optional[str] = None


_mcp_oauth_states: Dict[str, Dict[str, Any]] = {}
_mcp_oauth_lock = threading.Lock()


def _is_investment_trade_dict(t: Dict[str, Any]) -> bool:
    if not t:
        return False
    asset = str(t.get("asset") or "").upper()
    if asset in ("INVESTMENTS", "STOCK", "OPTION", "EQUITY"):
        return True
    meta = t.get("metadata")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    if isinstance(meta, dict):
        if str(meta.get("universe") or "").upper() == "INVESTMENTS":
            return True
        if str(meta.get("vehicle") or "").upper() in ("STOCK", "OPTION"):
            return True
    return False


@router.get("/session")
def get_session_status():
    """Returns current US Equity Market Session."""
    return {
        "success": True,
        "session": RobinhoodMarketSession.get_current_session()
    }


@router.get("/options-chain")
def get_options_chain(
    symbol: str = Query("SPY"),
    option_type: Optional[str] = Query(None),
    dte_window: str = Query("0DTE_WEEKLY"),
    current_user: dict = Depends(get_current_user)
):
    """
    Returns suggested ATM/Near-ATM option contracts and live quote for the symbol
    so selecting any symbol in the Order Ticket immediately populates realistic parameters.
    """
    sym = symbol.strip().upper()
    quote = get_live_stock_quote(sym)
    spot = float(quote.get("price") or 100.0)
    target_delta = float(current_user.get("investments_options_delta_target") or 0.45)

    best_call = OptionsContractSelector.select_best_contract(
        symbol=sym,
        bias="BULLISH",
        target_delta=target_delta,
        dte_window=dte_window,
        spot_override=spot
    )
    best_put = OptionsContractSelector.select_best_contract(
        symbol=sym,
        bias="BEARISH",
        target_delta=target_delta,
        dte_window=dte_window,
        spot_override=spot
    )

    preferred_type = (option_type or "CALL").upper()
    primary = best_call if preferred_type == "CALL" else best_put
    if not primary:
        primary = {
            "symbol": sym,
            "option_type": preferred_type,
            "strike": round(spot),
            "expiration": RobinhoodMarketSession.get_current_session()["now_iso"][:10],
            "theo_price": 1.50,
            "ask": 1.55,
            "bid": 1.45,
            "delta": 0.45 if preferred_type == "CALL" else -0.45,
            "theta": -0.05,
            "cost_per_contract": 155.0
        }

    return {
        "success": True,
        "symbol": sym,
        "spot_price": spot,
        "quote": quote,
        "suggested": primary,
        "call_contract": best_call,
        "put_contract": best_put,
        "optimal_call": best_call,
        "optimal_put": best_put,
    }


@router.get("/scanner")
def get_scanner_feed(
    symbols: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Returns real-time intraday scanner rankings, technical snapshots,
    breadth, suggested option contract details, and agentic dossiers for the user's watchlist.
    """
    if symbols:
        sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    else:
        sym_list = DynamicMarketScreener.resolve_tradeable_symbols(current_user)

    rankings = _scanner.scan_watchlist(sym_list)
    breadth = _scanner.get_market_breadth()
    session = RobinhoodMarketSession.get_current_session()

    cards = []
    client = RobinhoodClientFactory.get_client(current_user["id"], mode_override=current_user.get("trading_mode", "PAPER"))
    bp_data = client.get_buying_power()
    buying_power = float(bp_data.get("buying_power") or 0.0)

    etf_set = {"SPY", "QQQ", "IWM", "DIA", "TLT", "GLD", "SLV", "SMH", "XLF", "XLK", "XLE", "ARKK"}
    stock_tp_default = float(current_user.get("investments_stock_tp_pct") or 2.5)
    stock_sl_default = float(current_user.get("investments_stock_sl_pct") or 1.0)
    opt_tp_default = float(current_user.get("investments_option_tp_pct") or 35.0)
    opt_sl_default = float(current_user.get("investments_option_sl_pct") or 20.0)
    min_conf = float(current_user.get("investments_min_confidence") or 72.0)

    # In-play discovered market candidates metadata (for screener tags)
    in_play_meta = DynamicMarketScreener._cached_metadata

    for item in rankings:
        sym = item["symbol"]
        spot_px = float(item.get("price") or 100.0)
        bias = item.get("bias") or "BULLISH"
        is_bear = (bias == "BEARISH")
        conf = float(item.get("confidence") or 50.0)
        screener_tag = in_play_meta.get(sym, {}).get("tag")

        opt_contract = OptionsContractSelector.select_best_contract(
            symbol=sym,
            bias="BEARISH" if is_bear else "BULLISH",
            target_delta=float(current_user.get("investments_options_delta_target") or 0.45),
            dte_window=str(current_user.get("investments_options_dte_window") or "0DTE_WEEKLY"),
            spot_override=spot_px
        )
        stock_tp_price = round(spot_px * (1.0 - stock_tp_default / 100.0 if is_bear else 1.0 + stock_tp_default / 100.0), 2)
        stock_sl_price = round(spot_px * (1.0 + stock_sl_default / 100.0 if is_bear else 1.0 - stock_sl_default / 100.0), 2)

        decision = "EXECUTE" if (conf >= min_conf and bias != "NEUTRAL") else "MONITOR"
        dossier = {
            "thesis": f"{item.get('setup_type', 'CONSOLIDATION')} on {sym} at ${spot_px:.2f} (RVOL {item.get('rvol', 1.0)}x, VWAP ${item.get('vwap', spot_px):.2f}, RSI {item.get('rsi', 50.0)}).",
            "key_catalysts": item.get("reasons") or [f"RVOL {item.get('rvol', 1.0)}x", f"RSI {item.get('rsi', 50.0)}"],
            "conviction_score": conf,
            "risk_warning": f"Watch VWAP (${item.get('vwap', spot_px):.2f}) as intraday pivot."
        }

        rec_vehicle = "OPTION" if sym in ("SPY", "QQQ", "NVDA", "TSLA", "META", "AMD") else "STOCK"
        trend_label = "BULLISH EMA" if float(item.get("ema9") or 0) >= float(item.get("ema21") or 0) else "BEARISH EMA"

        cards.append({
            **item,
            "asset_class": "ETF" if sym in etf_set else "STOCK",
            "bid": round(spot_px * 0.9998, 2),
            "ask": round(spot_px * 1.0002, 2),
            "trend": trend_label,
            "agentic_decision": decision,
            "agentic_dossier": dossier,
            "recommended_vehicle": rec_vehicle,
            "stock_tp_price": stock_tp_price,
            "stock_sl_price": stock_sl_price,
            "stock_tp_pct": stock_tp_default,
            "stock_sl_pct": stock_sl_default,
            "option_tp_pct": opt_tp_default,
            "option_sl_pct": opt_sl_default,
            "suggested_strike": opt_contract["strike"] if opt_contract else round(spot_px),
            "suggested_expiration": opt_contract["expiration"] if opt_contract else session["now_iso"][:10],
            "suggested_option_type": opt_contract["option_type"] if opt_contract else ("PUT" if is_bear else "CALL"),
            "estimated_premium": opt_contract["ask"] if opt_contract else 1.50,
            "delta": opt_contract["delta"] if opt_contract else (-0.45 if is_bear else 0.45),
            "screener_tag": screener_tag
        })

    return {
        "success": True,
        "session": session,
        "breadth": breadth,
        "buying_power": buying_power,
        "screener_mode": str(current_user.get("investments_screener_mode") or "HYBRID").upper(),
        "items": cards
    }


@router.get("/portfolio")
def get_investments_portfolio(current_user: dict = Depends(get_current_user)):
    """Returns Robinhood buying power, active open investment positions, recent orders, and P&L stats."""
    user_id = current_user["id"]
    mode = str(current_user.get("trading_mode") or "PAPER").upper()

    client = RobinhoodClientFactory.get_client(user_id, mode_override=mode)
    bp_data = client.get_buying_power()
    raw_bp = bp_data.get("buying_power")
    if raw_bp is None:
        # Never show a fake $10k balance in LIVE mode when the broker query fails
        cash_bal = 0.0 if mode == "LIVE" else 10000.0
    else:
        cash_bal = float(raw_bp)

    stock_tp_default = float(current_user.get("investments_stock_tp_pct") or 2.5)
    stock_sl_default = float(current_user.get("investments_stock_sl_pct") or 1.0)
    opt_tp_default = float(current_user.get("investments_option_tp_pct") or 35.0)
    opt_sl_default = float(current_user.get("investments_option_sl_pct") or 20.0)
    max_open_positions = int(current_user.get("investments_max_open_positions") or 4)

    if mode == "LIVE":
        # Lightweight read-only reconciliation of pending LIVE entries/exits with the broker
        try:
            reconcile_live_trades(user_id, client)
            sync_broker_positions(user_id, client)
        except Exception as _re:
            logger.warning(f"[Investments] portfolio reconcile error user #{user_id}: {_re}")

    open_trades = [
        t for t in TradeStore.get_open_trades(user_id)
        if _is_investment_trade_dict(t) and str(t.get("mode") or "PAPER").upper() == mode
    ]
    formatted_positions = []
    open_market_value = 0.0
    total_unrealized_pnl = 0.0

    for t in open_trades:
        ticker = t.get("ticker", "")
        meta = t.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}

        sym = meta.get("symbol") or ticker.split("_")[0]
        vehicle = str(meta.get("vehicle") or "STOCK").upper()
        side = str(t.get("side") or "BUY").upper()
        entry_price = float(t.get("entry_price") or 1.0)
        count = float(t.get("count") or 1.0)
        quote = get_live_stock_quote(sym)
        quote_ok = quote_is_usable(quote)
        multiplier = 100.0 if vehicle == "OPTION" else 1.0

        delta_val = None
        strike_val = meta.get("strike")
        exp_val = meta.get("expiration")
        o_type = str(meta.get("option_type") or "CALL").upper()

        if vehicle == "STOCK":
            cur_price = float(quote.get("price") or entry_price) if quote_ok else entry_price
            tp_pct = float(meta.get("tp_pct") or stock_tp_default)
            sl_pct = float(meta.get("sl_pct") or stock_sl_default)
        elif not quote_ok:
            cur_price = entry_price
            tp_pct = float(meta.get("tp_pct") or opt_tp_default)
            sl_pct = float(meta.get("sl_pct") or opt_sl_default)
        else:
            spot = float(quote.get("price"))
            strike_f = float(strike_val or spot)
            cur_price, delta_val, _ = black_scholes_price(spot=spot, strike=strike_f, dte_days=1, option_type=o_type)
            tp_pct = float(meta.get("tp_pct") or opt_tp_default)
            sl_pct = float(meta.get("sl_pct") or opt_sl_default)

        is_short_stock = (vehicle == "STOCK" and side == "SELL")
        if is_short_stock:
            pnl_dollars = round((entry_price - cur_price) * count * multiplier, 2)
            pnl_pct = round(((entry_price - cur_price) / max(entry_price, 0.001)) * 100.0, 2)
            tp_price = round(entry_price * (1.0 - tp_pct / 100.0), 2)
            sl_price = round(entry_price * (1.0 + sl_pct / 100.0), 2)
        else:
            pnl_dollars = round((cur_price - entry_price) * count * multiplier, 2)
            pnl_pct = round(((cur_price - entry_price) / max(entry_price, 0.001)) * 100.0, 2)
            tp_price = round(entry_price * (1.0 + tp_pct / 100.0), 2)
            sl_price = round(entry_price * (1.0 - sl_pct / 100.0), 2)

        pos_market_val = round(cur_price * count * multiplier, 2)
        open_market_value += pos_market_val
        total_unrealized_pnl += pnl_dollars

        formatted_positions.append({
            "id": t.get("id"),
            "ticker": ticker,
            "symbol": sym,
            "vehicle": vehicle,
            "side": side,
            "entry_price": entry_price,
            "current_price": cur_price,
            "count": count,
            "market_value": pos_market_val,
            "pnl_dollars": pnl_dollars,
            "pnl_pct": pnl_pct,
            "tp_pct": tp_pct,
            "sl_pct": sl_pct,
            "tp_price": tp_price,
            "sl_price": sl_price,
            "strike": strike_val,
            "expiration": exp_val,
            "option_type": o_type if vehicle == "OPTION" else None,
            "delta": delta_val,
            "mode": t.get("mode") or mode,
            "reason": t.get("reason"),
            "trading_style": t.get("trading_style") or "MANUAL",
            "signal_source": t.get("signal_source") or "MANUAL",
            "timestamp": t.get("timestamp"),
            "quote_stale": not quote_ok,
            "pending_fill": bool(meta.get("pending_fill")),
            "pending_close": meta.get("pending_close"),
            "broker_state": meta.get("broker_state"),
            "metadata": meta
        })

    # Recent orders & realized P&L strictly for INVESTMENTS in active mode
    all_recent = TradeStore.get_recent_trades(user_id, limit=100)
    inv_trades = [
        t for t in all_recent
        if _is_investment_trade_dict(t) and str(t.get("mode") or "PAPER").upper() == mode
    ]

    recent_orders = []
    total_realized_pnl = 0.0
    wins = 0
    losses = 0

    open_by_id = {p["id"]: p for p in formatted_positions}

    for t in inv_trades:
        meta = t.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        tid = t.get("id")
        status = str(t.get("status") or "OPEN").upper()
        sym = meta.get("symbol") or str(t.get("ticker") or "").split("_")[0]
        vehicle = str(meta.get("vehicle") or "STOCK").upper()
        entry_px = float(t.get("entry_price") or 0.0)
        count_val = float(t.get("count") or 1.0)
        multiplier = 100.0 if vehicle == "OPTION" else 1.0
        tp_pct_val = float(meta.get("tp_pct") or (stock_tp_default if vehicle == "STOCK" else opt_tp_default))
        sl_pct_val = float(meta.get("sl_pct") or (stock_sl_default if vehicle == "STOCK" else opt_sl_default))

        if status == "OPEN" and tid in open_by_id:
            pos_info = open_by_id[tid]
            pnl_val = pos_info["pnl_dollars"]
            pnl_pct_val = pos_info["pnl_pct"]
            cur_px = pos_info["current_price"]
            exit_px = None
            tp_px = pos_info["tp_price"]
            sl_px = pos_info["sl_price"]
        else:
            exit_px = float(t.get("exit_price")) if t.get("exit_price") is not None else entry_px
            cur_px = exit_px
            raw_pnl = t.get("pnl_dollars") if t.get("pnl_dollars") is not None else t.get("pnl")
            pnl_val = round(float(raw_pnl or 0.0), 2)
            cost_basis = max(entry_px * count_val * multiplier, 0.01)
            pnl_pct_val = round((pnl_val / cost_basis) * 100.0, 2)
            is_short_order = (vehicle == "STOCK" and str(t.get("side") or "BUY").upper() == "SELL")
            tp_px = round(entry_px * (1.0 - tp_pct_val / 100.0 if is_short_order else 1.0 + tp_pct_val / 100.0), 2)
            sl_px = round(entry_px * (1.0 + sl_pct_val / 100.0 if is_short_order else 1.0 - sl_pct_val / 100.0), 2)
            if status != "OPEN":
                total_realized_pnl += pnl_val
                if pnl_val > 0:
                    wins += 1
                elif pnl_val < 0:
                    losses += 1

        recent_orders.append({
            "id": tid,
            "ticker": t.get("ticker"),
            "symbol": sym,
            "vehicle": vehicle,
            "side": t.get("side") or "BUY",
            "status": status,
            "entry_price": entry_px,
            "exit_price": exit_px,
            "current_price": cur_px,
            "count": count_val,
            "pnl": pnl_val,
            "pnl_dollars": pnl_val,
            "live_pnl": pnl_val if status == "OPEN" else None,
            "pnl_pct": pnl_pct_val,
            "tp_pct": tp_pct_val,
            "sl_pct": sl_pct_val,
            "tp_price": tp_px,
            "sl_price": sl_px,
            "strike": meta.get("strike"),
            "expiration": meta.get("expiration"),
            "option_type": meta.get("option_type"),
            "mode": t.get("mode") or mode,
            "reason": t.get("reason") or "MANUAL",
            "exit_reason": t.get("exit_reason"),
            "trading_style": t.get("trading_style") or "MANUAL",
            "signal_source": t.get("signal_source") or "MANUAL",
            "timestamp": t.get("timestamp"),
            "settled_at": t.get("settled_at"),
            "asset": "INVESTMENTS",
            "metadata": meta
        })

    total_closed = wins + losses
    win_rate = round((wins / total_closed) * 100.0, 1) if total_closed > 0 else 0.0
    net_portfolio_value = round(cash_bal + open_market_value, 2)
    day_pnl_dollars = round(total_realized_pnl + total_unrealized_pnl, 2)
    base_eq = max(net_portfolio_value - day_pnl_dollars, 1.0)
    day_pnl_pct = round((day_pnl_dollars / base_eq) * 100.0, 2)

    return {
        "success": True,
        "mode": mode,
        "open_count": len(formatted_positions),
        "buying_power": round(cash_bal, 2),
        "cash": round(cash_bal, 2),
        "open_market_value": round(open_market_value, 2),
        "portfolio_value": net_portfolio_value,
        "day_pnl_dollars": day_pnl_dollars,
        "day_pnl_pct": day_pnl_pct,
        "total_realized_pnl": round(total_realized_pnl, 2),
        "total_unrealized_pnl": round(total_unrealized_pnl, 2),
        "win_rate": win_rate,
        "wins": wins,
        "losses": losses,
        "max_open_positions": max_open_positions,
        "pdt_status": "UNRESTRICTED (PDT Rule Removed June 2026)",
        "positions": formatted_positions,
        "recent_orders": recent_orders[:40]
    }


@router.post("/trade/stock")
def manual_stock_trade(
    req: ManualStockOrderRequest,
    current_user: dict = Depends(get_current_user)
):
    """Executes a 1-click manual stock or ETF trade (supports share count or dollar notional)."""
    user_id = current_user["id"]
    mode = str(current_user.get("trading_mode", "PAPER") or "PAPER").upper()

    # Risk Engine Check
    risk_status = RiskEngine.get_risk_status(user_id)
    if risk_status.get("kill_switch"):
        raise HTTPException(status_code=403, detail="Trading halted: Emergency Kill-Switch is active.")

    client = RobinhoodClientFactory.get_client(user_id, mode_override=mode)
    is_mcp = isinstance(client, RobinhoodMCPAdapter)

    sym = req.symbol.strip().upper()
    quote = get_decision_quote(sym, client if mode == "LIVE" else None)
    live_px = float(quote.get("ask") or quote.get("price")) if quote else None

    use_dollar_amount = (is_mcp and not (req.shares and req.shares > 0)
                         and req.notional_dollars and req.notional_dollars > 0
                         and str(req.order_type).upper() == "MARKET")
    is_limit = str(req.order_type).upper() == "LIMIT" and req.limit_price
    if live_px is None and not use_dollar_amount and not (is_limit and req.shares and req.shares > 0):
        # Never size or price an order from a placeholder quote
        raise HTTPException(status_code=503, detail=f"No live quote available for {sym}; order not sent.")

    shares = float(req.shares or 0.0)
    if shares <= 0 and req.notional_dollars and req.notional_dollars > 0 and live_px:
        allow_frac = bool(current_user.get("investments_allow_fractional") if current_user.get("investments_allow_fractional") is not None else 1)
        if allow_frac:
            shares = round(float(req.notional_dollars) / max(live_px, 0.01), 4)
        else:
            shares = float(int(float(req.notional_dollars) / max(live_px, 0.01)))

    if shares <= 0 and not use_dollar_amount:
        raise HTTPException(status_code=400, detail="Order size resolves to 0 shares; specify shares or a larger notional.")

    order_kwargs = {}
    if use_dollar_amount:
        order_kwargs["dollar_amount"] = float(req.notional_dollars)

    res = client.place_stock_order(
        symbol=sym,
        action=req.action,
        shares=shares,
        order_type=req.order_type,
        limit_price=req.limit_price,
        **order_kwargs
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Stock order failed."))
    shares = float(res.get("shares") or shares)

    trade_id = res.get("order_id")
    now_ny = RobinhoodMarketSession.get_current_session()["ny_time"]
    tp_pct = float(req.tp_pct if req.tp_pct is not None else (current_user.get("investments_stock_tp_pct") or 2.5))
    sl_pct = float(req.sl_pct if req.sl_pct is not None else (current_user.get("investments_stock_sl_pct") or 1.0))
    broker_state = str(res.get("state") or res.get("status") or "").lower()
    is_filled = bool(res.get("filled_price")) and (mode != "LIVE" or broker_state == "filled")
    pending_fill = mode == "LIVE" and not is_filled
    filled_px = float(res.get("filled_price") or res.get("estimated_price") or live_px or req.limit_price or 0.0)

    trade_rec = {
        "id": trade_id,
        "user_id": user_id,
        "ticker": sym,
        "side": req.action.upper(),
        "entry_price": filled_px,
        "count": shares,
        "status": "OPEN",
        "pnl": 0.0,
        "mode": mode,
        "reason": f"MANUAL_STOCK_{req.action.upper()} ({shares} sh @ ${filled_px:.2f}{' est, pending fill' if pending_fill else ''})",
        "trading_style": "MANUAL",
        "signal_source": "MANUAL",
        "timestamp": now_ny,
        "asset": "INVESTMENTS",
        "metadata": json.dumps({
            "universe": "INVESTMENTS",
            "vehicle": "STOCK",
            "symbol": sym,
            "shares": shares,
            "order_type": req.order_type,
            "tp_pct": tp_pct,
            "sl_pct": sl_pct,
            "broker": res.get("broker") or ("PAPER" if mode == "PAPER" else None),
            "broker_status": res.get("status"),
            "broker_state": broker_state or None,
            "pending_fill": pending_fill,
            "estimated_entry": pending_fill,
            "dollar_amount": order_kwargs.get("dollar_amount"),
            "account_number": res.get("account_number")
        })
    }
    TradeStore.insert_trade(user_id, trade_rec)
    return {"success": True, "trade": trade_rec, "pending_fill": pending_fill, "broker_state": broker_state}


@router.post("/order/{trade_id}/cancel")
def cancel_investment_order(trade_id: str, current_user: dict = Depends(get_current_user)):
    """Cancels a not-yet-filled LIVE Robinhood (Agentic MCP) order. Marks the trade CANCELLED only
    when the broker confirms the cancel; partial fills keep the filled quantity open."""
    user_id = current_user["id"]
    target = next((t for t in TradeStore.get_open_trades(user_id)
                   if t.get("id") == trade_id and _is_investment_trade_dict(t)), None)
    if not target:
        raise HTTPException(status_code=404, detail="Open investment order not found.")
    meta = parse_meta(target)
    if str(target.get("mode") or "PAPER").upper() != "LIVE":
        raise HTTPException(status_code=400, detail="Paper orders fill instantly — use Close instead.")

    client = RobinhoodClientFactory.get_client(user_id, mode_override="LIVE")
    if not hasattr(client, "cancel_order"):
        raise HTTPException(status_code=400, detail="Cancel is only supported for Robinhood Agentic (MCP) orders.")
    vehicle = str(meta.get("vehicle") or "STOCK").upper()
    res = client.cancel_order(trade_id, vehicle=vehicle)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error") or "Cancel rejected by Robinhood.")

    state = str(res.get("state") or "").lower()
    if state in ("cancelled", "canceled"):
        # Let the reconciler handle partial-fill-then-cancel (keeps filled qty) vs full cancel
        stats = reconcile_live_trades(user_id, client, [target]) if meta.get("pending_fill") else {}
        if not meta.get("pending_fill"):
            meta.update({"broker_state": state})
            TradeStore.update_trade(trade_id, {
                "status": "CANCELLED", "exit_price": target.get("entry_price"), "pnl": 0.0, "pnl_dollars": 0.0,
                "exit_reason": "ORDER_CANCELLED", "settled_at": time.time(),
                "closed_at": RobinhoodMarketSession.get_current_session()["ny_time"],
                "metadata": json.dumps(meta)
            }, only_if_open=True)
        return {"success": True, "trade_id": trade_id, "broker_state": state, "reconcile": stats}
    if "fill" in state:
        reconcile_live_trades(user_id, client, [target])
        raise HTTPException(status_code=409, detail=f"Order already {state} — use Close to exit the position.")

    update_meta(target, {"cancel_requested_at": time.time(), "broker_state": state or "pending_cancelled"})
    return {"success": True, "trade_id": trade_id, "broker_state": state or "pending_cancelled",
            "message": "Cancel requested; trade stays open until Robinhood confirms the cancel."}


@router.post("/trade/option")
def manual_option_trade(
    req: ManualOptionOrderRequest,
    current_user: dict = Depends(get_current_user)
):
    """Executes a 1-click manual equity options trade."""
    user_id = current_user["id"]
    mode = str(current_user.get("trading_mode", "PAPER") or "PAPER").upper()

    # Risk Engine Check
    risk_status = RiskEngine.get_risk_status(user_id)
    if risk_status.get("kill_switch"):
        raise HTTPException(status_code=403, detail="Trading halted: Emergency Kill-Switch is active.")

    client = RobinhoodClientFactory.get_client(user_id, mode_override=mode)

    sym = req.symbol.strip().upper()
    res = client.place_option_order(
        symbol=sym,
        strike=req.strike,
        expiration=req.expiration,
        option_type=req.option_type,
        action=req.action,
        contracts=req.contracts,
        order_type=req.order_type,
        limit_price=req.limit_price
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Options order failed."))

    trade_id = res.get("order_id")
    now_ny = RobinhoodMarketSession.get_current_session()["ny_time"]
    tp_pct = float(req.tp_pct if req.tp_pct is not None else (current_user.get("investments_option_tp_pct") or 35.0))
    sl_pct = float(req.sl_pct if req.sl_pct is not None else (current_user.get("investments_option_sl_pct") or 20.0))
    broker_state = str(res.get("state") or res.get("status") or "").lower()
    is_filled = bool(res.get("filled_price")) and (mode != "LIVE" or broker_state == "filled")
    pending_fill = mode == "LIVE" and not is_filled
    filled_px = float(res.get("filled_price") or res.get("estimated_price") or req.limit_price or 0.0)

    trade_rec = {
        "id": trade_id,
        "user_id": user_id,
        "ticker": res.get("contract_ticker", f"{sym}_{req.expiration}_{req.option_type.upper()}_{req.strike}"),
        "side": req.action.upper(),
        "entry_price": filled_px,
        "count": req.contracts,
        "status": "OPEN",
        "pnl": 0.0,
        "mode": mode,
        "reason": f"MANUAL_OPTION_{req.option_type.upper()} ({req.contracts}x ${req.strike} {req.option_type.upper()} @ ${filled_px:.2f}{' est, pending fill' if pending_fill else ''})",
        "trading_style": "MANUAL",
        "signal_source": "MANUAL",
        "timestamp": now_ny,
        "asset": "INVESTMENTS",
        "metadata": json.dumps({
            "universe": "INVESTMENTS",
            "vehicle": "OPTION",
            "symbol": sym,
            "strike": req.strike,
            "expiration": req.expiration,
            "option_type": req.option_type.upper(),
            "contracts": req.contracts,
            "order_type": req.order_type,
            "tp_pct": tp_pct,
            "sl_pct": sl_pct,
            "option_id": res.get("option_id"),
            "broker": res.get("broker") or ("PAPER" if mode == "PAPER" else None),
            "broker_state": broker_state or None,
            "pending_fill": pending_fill,
            "estimated_entry": pending_fill
        })
    }
    TradeStore.insert_trade(user_id, trade_rec)
    return {"success": True, "trade": trade_rec, "pending_fill": pending_fill, "broker_state": broker_state}


@router.post("/close/{trade_id}")
def close_investment_trade(
    trade_id: str,
    current_user: dict = Depends(get_current_user),
    allow_queue: bool = False
):
    """Closes an open investment position.

    PAPER: settles instantly at the live quote (refuses placeholder quotes).
    LIVE: sends the real opposite-side order to the broker (sell-to-close long, buy-to-cover
    short, option sell/buy-to-close). The trade is CLOSED only on a confirmed broker fill;
    queued orders keep it OPEN with metadata.pending_close; rejections raise HTTP 400."""
    user_id = current_user["id"]
    open_trades = TradeStore.get_open_trades(user_id)
    target = next((t for t in open_trades if t.get("id") == trade_id and _is_investment_trade_dict(t)), None)
    if not target:
        raise HTTPException(status_code=404, detail="Open investment trade not found.")

    meta = parse_meta(target)
    mode = str(target.get("mode") or "PAPER").upper()

    if mode == "LIVE":
        session = RobinhoodMarketSession.get_current_session()
        if not session.get("is_regular_hours") and not allow_queue:
            raise HTTPException(
                status_code=400,
                detail="US markets are closed. Placing a market exit order now will queue it for the next open (gap risk). Pass allow_queue=true if confirmed."
            )
        client = RobinhoodClientFactory.get_client(user_id, mode_override="LIVE")
        res = submit_exit(user_id, target, client, "MANUAL_CLOSE")
        if res.get("status") == "ERROR":
            raise HTTPException(status_code=400, detail=res.get("error") or "Robinhood rejected the close order.")
        if res.get("status") == "PENDING_CLOSE":
            return {"success": True, "trade_id": trade_id, "status": "PENDING_CLOSE",
                    "order_id": res.get("order_id"), "broker_state": res.get("broker_state"),
                    "pnl": None, "exit_reason": "MANUAL_CLOSE",
                    "message": res.get("message") or "Close order submitted; position closes when Robinhood reports the fill."}
        return {"success": True, "trade_id": trade_id, "status": "CLOSED", "order_id": res.get("order_id"),
                "exit_price": res.get("exit_price"), "pnl": res.get("pnl"), "exit_reason": "MANUAL_CLOSE"}

    sym = meta.get("symbol") or target.get("ticker", "").split("_")[0]
    vehicle = str(meta.get("vehicle") or "STOCK").upper()
    side = str(target.get("side") or "BUY").upper()

    quote = get_decision_quote(sym)
    if not quote:
        raise HTTPException(status_code=503, detail=f"No live quote available for {sym}; close not processed.")
    if vehicle == "STOCK":
        cur_price = quote["ask"] if side == "SELL" else quote["bid"]
    else:
        spot = quote["price"]
        strike = float(meta.get("strike") or spot)
        o_type = str(meta.get("option_type") or "CALL")
        try:
            dte = max((datetime.date.fromisoformat(str(meta.get("expiration"))) - datetime.datetime.now(ZoneInfo("America/New_York")).date()).days, 0)
        except Exception:
            dte = 1
        cur_price, _, _ = black_scholes_price(spot=spot, strike=strike, dte_days=dte, option_type=o_type)

    pnl_dollars = compute_pnl(target, cur_price, vehicle)

    now_ny = RobinhoodMarketSession.get_current_session()["ny_time"]
    if TradeStore.close_if_open(user_id, target, {
        "status": "CLOSED",
        "exit_price": cur_price,
        "pnl": pnl_dollars,
        "pnl_dollars": pnl_dollars,
        "exit_reason": "MANUAL_CLOSE",
        "settled_at": time.time(),
        "closed_at": now_ny
    }):
        settle_paper_balance(user_id, target, cur_price)

    return {
        "success": True,
        "trade_id": trade_id,
        "status": "CLOSED",
        "exit_price": cur_price,
        "pnl": pnl_dollars,
        "exit_reason": "MANUAL_CLOSE"
    }


@router.post("/close_all")
@router.post("/close-all")
def close_all_investment_trades(current_user: dict = Depends(get_current_user)):
    """Emergency closes all open investment trades; reports per-trade results and errors."""
    user_id = current_user["id"]
    open_trades = [t for t in TradeStore.get_open_trades(user_id) if _is_investment_trade_dict(t)]
    closed = 0
    pending = []
    errors = []
    total_pnl = 0.0
    for t in open_trades:
        try:
            res = close_investment_trade(t["id"], current_user)
            if res.get("status") == "PENDING_CLOSE":
                pending.append({"trade_id": t["id"], "order_id": res.get("order_id"), "broker_state": res.get("broker_state")})
            else:
                closed += 1
                total_pnl += float(res.get("pnl") or 0.0)
        except HTTPException as he:
            errors.append({"trade_id": t["id"], "ticker": t.get("ticker"), "error": str(he.detail)})
        except Exception as e:
            errors.append({"trade_id": t["id"], "ticker": t.get("ticker"), "error": str(e)})
    return {
        "success": not errors,
        "closed_count": closed,
        "pending_count": len(pending),
        "pending": pending,
        "error_count": len(errors),
        "errors": errors,
        "total_pnl": round(total_pnl, 2)
    }


@router.get("/config")
def get_user_investments_config(current_user: dict = Depends(get_current_user)):
    """Returns current user's investment universe configurations."""
    u = get_user_by_id(current_user["id"]) or current_user
    return {
        "success": True,
        "investments_paper_balance": float(u.get("investments_paper_balance") or 10000.0),
        "investments_trade_size_dollars": float(u.get("investments_trade_size_dollars") or 250.0),
        "investments_paper_trade_size_dollars": float(u.get("investments_paper_trade_size_dollars") or 500.0),
        "investments_asset_classes": u.get("investments_asset_classes") or "STOCKS,ETFS,OPTIONS",
        "investments_screener_mode": u.get("investments_screener_mode") or "HYBRID",
        "investments_watchlist": u.get("investments_watchlist") or "SPY,QQQ,NVDA,TSLA,AAPL,META,AMD,AMZN,MSFT,IWM",
        "investments_strategy": u.get("investments_strategy") or "ALL",
        "investments_min_confidence": float(u.get("investments_min_confidence") or 72.0),
        "investments_min_rvol": float(u.get("investments_min_rvol") or 1.3),
        "investments_max_daily_trades": int(u.get("investments_max_daily_trades") or 8),
        "investments_max_open_positions": int(u.get("investments_max_open_positions") or 4),
        "investments_max_daily_risk": float(u.get("investments_max_daily_risk") or 500.0),
        "investments_stock_tp_pct": float(u.get("investments_stock_tp_pct") or 2.5),
        "investments_stock_sl_pct": float(u.get("investments_stock_sl_pct") or 1.0),
        "investments_option_tp_pct": float(u.get("investments_option_tp_pct") or 35.0),
        "investments_option_sl_pct": float(u.get("investments_option_sl_pct") or 20.0),
        "investments_trailing_stop_enabled": bool(u.get("investments_trailing_stop_enabled") if u.get("investments_trailing_stop_enabled") is not None else 1),
        "investments_trailing_stop_pct": float(u.get("investments_trailing_stop_pct") or 0.8),
        "investments_eod_auto_flatten": bool(u.get("investments_eod_auto_flatten") if u.get("investments_eod_auto_flatten") is not None else 1),
        "investments_extended_hours": bool(u.get("investments_extended_hours") or 0),
        "investments_allow_fractional": bool(u.get("investments_allow_fractional") if u.get("investments_allow_fractional") is not None else 1),
        "investments_options_delta_target": float(u.get("investments_options_delta_target") or 0.45),
        "investments_options_dte_window": u.get("investments_options_dte_window") or "0DTE_WEEKLY",
        "investments_options_max_spread_pct": float(u.get("investments_options_max_spread_pct") or 8.0),
        "investments_options_min_oi": int(u.get("investments_options_min_oi") or 250),
        "investments_use_kelly": bool(u.get("investments_use_kelly") if u.get("investments_use_kelly") is not None else 1),
        "investments_live_autotrade_enabled": bool(u.get("investments_live_autotrade_enabled", 0)),
        "investments_live_max_dollars_per_day": float(u.get("investments_live_max_dollars_per_day") or 25.0),
        "investments_risk_per_trade_pct": float(u.get("investments_risk_per_trade_pct") or 1.0),
        "investments_max_exposure_pct": float(u.get("investments_max_exposure_pct") or 50.0),
        "investments_max_consecutive_losses": int(u.get("investments_max_consecutive_losses") or 3),
        "investments_cooldown_minutes": int(u.get("investments_cooldown_minutes") or 60),
        "investments_kill_switch": bool(u.get("investments_kill_switch", 0)),
        "rh_auth_mode": u.get("rh_auth_mode") or "ROBINHOOD_MCP",
        "rh_account_type": u.get("rh_account_type") or "CASH",
        "rh_mcp_url": u.get("rh_mcp_url") or DEFAULT_ROBINHOOD_MCP_URL,
        "has_mcp_token": bool(u.get("rh_mcp_token_enc")),
        "has_robinhood_keys": bool(
            u.get("rh_mcp_token_enc") or
            (u.get('rh_username_enc') and u.get('rh_password_enc')) or
            (u.get('rh_api_key_id') and u.get('rh_api_private_key_enc'))
        )
    }


@router.get("/risk/status")
def get_investments_risk_status(current_user: dict = Depends(get_current_user)):
    """Returns institutional risk metrics, limits, circuit-breaker cooldowns, and kill-switch status."""
    user_id = current_user["id"]
    return {
        "success": True,
        "risk": RiskEngine.get_risk_status(user_id)
    }


@router.post("/risk/kill-switch")
def toggle_investments_kill_switch(
    active: bool = True,
    flatten_positions: bool = True,
    current_user: dict = Depends(get_current_user)
):
    """Emergency trading kill-switch: halts auto-trading and optionally flattens all open positions."""
    user_id = current_user["id"]
    now_ts = time.time() if active else None
    update_user_investments_config(user_id, {
        "investments_kill_switch": 1 if active else 0,
        "investments_kill_switch_at": now_ts,
        "investments_live_autotrade_enabled": 0 if active else None
    })
    flatten_res = None
    if active and flatten_positions:
        flatten_res = close_all_investment_trades(current_user)
    return {
        "success": True,
        "kill_switch_active": active,
        "flatten_result": flatten_res,
        "risk_status": RiskEngine.get_risk_status(user_id)
    }


@router.get("/screener/in-play")
def get_discovered_in_play_candidates(
    limit: int = Query(15, ge=1, le=30),
    force: bool = Query(False),
    current_user: dict = Depends(get_current_user)
):
    """
    Returns dynamically screened intraday in-play stocks across US equities
    filtered by minimum price, volume, and momentum volatility.
    """
    candidates = DynamicMarketScreener.discover_in_play_stocks(limit=limit, force_refresh=force)
    return {
        "success": True,
        "count": len(candidates),
        "candidates": candidates
    }


@router.get("/performance/status")
def get_investments_performance_status(current_user: dict = Depends(get_current_user)):
    """Returns win rates, expectancy, and status per setup type."""
    user_id = current_user["id"]
    return PerformanceTracker.get_setup_performance(user_id)


@router.get("/macro/status")
def get_investments_macro_status(current_user: dict = Depends(get_current_user)):
    """Returns Kalshi prediction market lead-lag indicators and macroeconomic event state."""
    from backend.investments.macro_catalyst_engine import MacroCatalystEngine
    return {
        "success": True,
        "lead_lag": MacroCatalystEngine.get_kalshi_macro_lead_lag()
    }


@router.get("/tape/flow/{symbol}")
def get_investments_order_flow(symbol: str, current_user: dict = Depends(get_current_user)):
    """Returns sub-second order flow analytics, CVD delta ratio, and block sweep summaries."""
    from backend.investments.subsecond_tape_engine import SubSecondTapeEngine
    return {
        "success": True,
        "flow": SubSecondTapeEngine.get_order_flow_analytics(symbol)
    }


@router.websocket("/ws/tape")
async def investments_tape_websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    """
    Real-time Sub-Second Level 2 Tape Streaming WebSocket endpoint.
    Streams sub-millisecond prints, Cumulative Volume Delta (CVD), and block sweep alerts.
    """
    await websocket.accept()
    # Authenticate via JWT token parameter or cookies if provided
    auth_user = None
    if token:
        payload = decode_jwt_token(token)
        if payload and payload.get("user_id"):
            auth_user = payload
    if not auth_user and "saas_token" in websocket.cookies:
        payload = decode_jwt_token(websocket.cookies["saas_token"])
        if payload and payload.get("user_id"):
            auth_user = payload

    from backend.investments.subsecond_tape_engine import SubSecondTapeEngine
    SubSecondTapeEngine.register_subscriber(websocket)
    try:
        # Send initial handshake with active watchlist analytics
        await websocket.send_json({
            "type": "TAPE_CONNECTED",
            "authenticated": auth_user is not None,
            "timestamp": time.time(),
            "message": "Sub-Second Level 2 Tape & Order Flow WebSocket connected"
        })
        while True:
            # Keep connection alive & handle incoming ping/subscribe messages
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_json({"type": "pong", "time": time.time()})
            else:
                try:
                    data = json.loads(msg)
                    if data.get("action") == "GET_FLOW" and data.get("symbol"):
                        sym = str(data["symbol"]).upper()
                        flow = SubSecondTapeEngine.get_order_flow_analytics(sym)
                        await websocket.send_json({
                            "type": "FLOW_UPDATE",
                            "symbol": sym,
                            "flow": flow
                        })
                except Exception:
                    pass
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        SubSecondTapeEngine.unregister_subscriber(websocket)


@router.get("/genetic/champion")
def get_investments_genetic_champion(current_user: dict = Depends(get_current_user)):
    """Evolves and returns the champion trading strategy genome."""
    from backend.investments.genetic_evolver import GeneticStrategyEvolver
    return GeneticStrategyEvolver.evolve_population(generations=2)


@router.get("/mcp/status")
def get_robinhood_mcp_status(current_user: dict = Depends(get_current_user)):
    """Returns Robinhood Agentic MCP server configuration & standard tools."""
    u = get_user_by_id(current_user["id"]) or current_user
    mcp_url = u.get("rh_mcp_url") or DEFAULT_ROBINHOOD_MCP_URL
    has_token = bool(u.get("rh_mcp_token_enc"))
    return {
        "success": True,
        "mcp_url": mcp_url,
        "has_mcp_token": has_token,
        "auth_mode": u.get("rh_auth_mode") or "ROBINHOOD_MCP",
        "standard_tools": ROBINHOOD_MCP_STANDARD_TOOLS
    }


@router.post("/mcp/test")
def test_robinhood_mcp_connection(
    req: Optional[MCPTestRequest] = Body(default=None),
    current_user: dict = Depends(get_current_user)
):
    """Tests connectivity and tool discovery against https://agent.robinhood.com/mcp/trading."""
    url_ov = req.mcp_url if (req and req.mcp_url) else None
    tok_ov = req.mcp_token if (req and req.mcp_token) else None
    adapter = RobinhoodMCPAdapter(
        user_id=current_user["id"],
        mcp_url_override=url_ov,
        token_override=tok_ov
    )
    return adapter.test_connection()


@router.post("/mcp/oauth/start")
def start_robinhood_mcp_oauth(
    request: Request,
    req: Optional[MCPOAuthStartRequest] = Body(default=None),
    current_user: dict = Depends(get_current_user)
):
    """
    Initiates RFC 7591 Dynamic Client Registration + OAuth 2.0 PKCE (S256) flow
    against Robinhood's official Agentic Trading MCP Server (`agent.robinhood.com`).
    Uses Robinhood's whitelisted redirect_uri (`cursor://anysphere.cursor-mcp/oauth/callback`
    by default so `robinhood.com/oauth` never rejects with a 403 Redirect URI mismatch).
    """
    user_id = current_user["id"]
    u = get_user_by_id(user_id) or current_user
    mcp_url = (u.get("rh_mcp_url") or DEFAULT_ROBINHOOD_MCP_URL).strip()

    # Default to the dashboard's own callback (Robinhood DCR accepts localhost redirect URIs);
    # the cursor:// scheme appears to be rejected on "Allow" when not initiated from Cursor.
    redirect_mode = "LOCAL_CALLBACK"

    if redirect_mode == "CURSOR_SCHEME":
        redirect_uri = "cursor://anysphere.cursor-mcp/oauth/callback"
    elif redirect_mode == "CLAUDE_WEB":
        redirect_uri = "https://claude.ai/api/mcp/auth_callback"
    else:
        origin = (req.origin if (req and req.origin) else "").strip().rstrip("/")
        if not origin:
            fwd_proto = request.headers.get("x-forwarded-proto")
            fwd_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
            if fwd_host:
                scheme = fwd_proto or ("https" if "ngrok" in fwd_host else request.url.scheme)
                origin = f"{scheme}://{fwd_host}"
            else:
                origin = str(request.base_url).rstrip("/")
        redirect_uri = f"{origin}/api/engine/investments/mcp/oauth/callback"

    # Step 1: Dynamic Client Registration via https://agent.robinhood.com/oauth/trading/register
    reg_url = "https://agent.robinhood.com/oauth/trading/register"
    reg_payload = {
        "client_name": "ShadowTrader AI",
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none"
    }

    try:
        reg_resp = requests.post(reg_url, json=reg_payload, timeout=8.0)
        if reg_resp.status_code not in (200, 201):
            raise HTTPException(
                status_code=502,
                detail=f"Robinhood OAuth client registration failed (HTTP {reg_resp.status_code}): {reg_resp.text[:200]}"
            )
        reg_data = reg_resp.json()
        client_id = reg_data.get("client_id") or "LtLiNmbs9owbYfWgBlC68Z2VujIPuvGoAiSYr8xW"
    except HTTPException:
        raise
    except Exception:
        client_id = "LtLiNmbs9owbYfWgBlC68Z2VujIPuvGoAiSYr8xW"

    # Step 2: Generate PKCE code_verifier & S256 code_challenge
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    state = secrets.token_urlsafe(32)

    now = time.time()
    with _mcp_oauth_lock:
        expired = [k for k, v in _mcp_oauth_states.items() if (now - v.get("created_at", 0)) > 900]
        for k in expired:
            _mcp_oauth_states.pop(k, None)
        _mcp_oauth_states[state] = {
            "user_id": user_id,
            "client_id": client_id,
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
            "mcp_url": mcp_url,
            "created_at": now
        }

    # Step 3: Build Robinhood OAuth authorization URL
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "internal",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
        "resource": mcp_url
    }
    auth_url = f"https://robinhood.com/oauth?{urllib.parse.urlencode(params)}"

    return {
        "success": True,
        "auth_url": auth_url,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "redirect_mode": redirect_mode,
        "state": state
    }


@router.post("/mcp/oauth/exchange")
def exchange_robinhood_mcp_oauth_code(
    req: MCPOAuthExchangeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Exchanges either a pasted redirect URL (`cursor://anysphere.cursor-mcp/oauth/callback?code=...&state=...`)
    or a raw authorization `code` for the user's Robinhood Agentic MCP Bearer `access_token` & `refresh_token`.
    """
    raw = (req.callback_url_or_code or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Please paste the redirect URL or authorization code.")

    code = None
    state = (req.state or "").strip() or None

    if "code=" in raw or "://" in raw or raw.startswith("?"):
        q_str = raw.split("?", 1)[1] if "?" in raw else raw
        parsed_q = urllib.parse.parse_qs(q_str)
        if "code" in parsed_q and parsed_q["code"]:
            code = parsed_q["code"][0].strip()
        if "state" in parsed_q and parsed_q["state"]:
            state = parsed_q["state"][0].strip()
    else:
        code = raw

    if not code:
        raise HTTPException(status_code=400, detail="Could not extract an authorization `code` from the input.")

    st_data = None
    with _mcp_oauth_lock:
        if state and state in _mcp_oauth_states:
            st_data = _mcp_oauth_states.pop(state, None)
        else:
            # Find most recent state for this user_id
            user_states = [
                (k, v) for k, v in _mcp_oauth_states.items()
                if v.get("user_id") == current_user["id"]
            ]
            if user_states:
                user_states.sort(key=lambda item: item[1].get("created_at", 0), reverse=True)
                latest_k, st_data = user_states[0]
                _mcp_oauth_states.pop(latest_k, None)

    if not st_data:
        raise HTTPException(
            status_code=400,
            detail="OAuth session expired or not found. Click 'Sign in with Robinhood OAuth' first, then paste the callback URL/code."
        )

    user_id = current_user["id"]
    client_id = st_data["client_id"]
    code_verifier = st_data["code_verifier"]
    redirect_uri = st_data["redirect_uri"]
    mcp_url = st_data["mcp_url"]

    token_url = "https://api.robinhood.com/oauth2/token/"
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier
    }
    try:
        tok_resp = requests.post(
            token_url,
            data=token_data,
            headers={"Accept": "application/json", "User-Agent": "ShadowTraderAI-MCPClient/3.0"},
            timeout=10.0
        )
        if tok_resp.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"Robinhood token exchange returned HTTP {tok_resp.status_code}: {tok_resp.text[:250]}"
            )
        tok_json = tok_resp.json()
        access_token = tok_json.get("access_token")
        refresh_token = tok_json.get("refresh_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="Robinhood response did not contain an access_token.")

        save_user_robinhood_credentials(
            user_id=user_id,
            mcp_url=mcp_url,
            mcp_token_enc=encrypt_kalshi_key(access_token.strip()),
            mcp_refresh_token_enc=encrypt_kalshi_key(refresh_token.strip()) if refresh_token else None,
            mcp_client_id=client_id,
            auth_mode="ROBINHOOD_MCP"
        )
        return {
            "success": True,
            "message": "Robinhood Agentic MCP OAuth Bearer & Refresh tokens encrypted and saved!",
            "mcp_url": mcp_url,
            "has_refresh_token": bool(refresh_token)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token exchange error: {e}")


@router.get("/mcp/oauth/callback", response_class=HTMLResponse)
def robinhood_mcp_oauth_callback(
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    error_description: Optional[str] = Query(default=None)
):
    """
    OAuth 2.0 Redirect Callback for Robinhood Agentic MCP.
    Exchanges authorization `code` + PKCE `code_verifier` for Bearer `access_token` & `refresh_token`,
    encrypts and stores them for the user, and notifies the opener window via `postMessage`.
    """
    def _render_popup_html(success: bool, title: str, subtitle: str) -> HTMLResponse:
        color = "#10b981" if success else "#f43f5e"
        icon = "✅" if success else "❌"
        payload_js = json.dumps({"type": "ROBINHOOD_MCP_OAUTH_RESULT", "success": success, "message": subtitle})
        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{
    background: #0b0f19;
    color: #f3f4f6;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100vh;
    margin: 0;
    padding: 20px;
    box-sizing: border-box;
  }}
  .card {{
    background: #131b2c;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 28px;
    max-width: 420px;
    width: 100%;
    text-align: center;
    box-shadow: 0 20px 50px rgba(0,0,0,0.6);
  }}
  .icon {{ font-size: 40px; margin-bottom: 12px; }}
  h2 {{ color: {color}; margin: 0 0 8px; font-size: 18px; }}
  p {{ color: #9ca3af; font-size: 13px; line-height: 1.5; margin: 0 0 20px; }}
  button {{
    background: {color};
    color: #000;
    border: none;
    border-radius: 10px;
    padding: 10px 20px;
    font-weight: 700;
    font-size: 13px;
    cursor: pointer;
  }}
</style>
</head>
<body>
  <div class="card">
    <div class="icon">{icon}</div>
    <h2>{title}</h2>
    <p>{subtitle}</p>
    <button onclick="window.close()">Close Window</button>
  </div>
  <script>
    try {{
      if (window.opener && !window.opener.closed) {{
        window.opener.postMessage({payload_js}, "*");
      }}
    }} catch (e) {{}}
    if ({'true' if success else 'false'}) {{
      setTimeout(function() {{ window.close(); }}, 1800);
    }}
  </script>
</body>
</html>"""
        return HTMLResponse(content=html, status_code=200)

    if error:
        return _render_popup_html(
            False,
            "Robinhood OAuth Authorization Declined",
            f"{error}: {error_description or 'Authorization was cancelled or denied.'}"
        )

    if not code or not state:
        return _render_popup_html(
            False,
            "Invalid OAuth Callback",
            "Missing authorization code or state parameter from Robinhood."
        )

    with _mcp_oauth_lock:
        st_data = _mcp_oauth_states.pop(state, None)

    if not st_data:
        return _render_popup_html(
            False,
            "OAuth Session Expired",
            "This OAuth session expired or was already used. Please click 'Sign in with Robinhood OAuth' again."
        )

    user_id = st_data["user_id"]
    client_id = st_data["client_id"]
    code_verifier = st_data["code_verifier"]
    redirect_uri = st_data["redirect_uri"]
    mcp_url = st_data["mcp_url"]

    # Exchange authorization code for Bearer token at https://api.robinhood.com/oauth2/token/
    token_url = "https://api.robinhood.com/oauth2/token/"
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier
    }
    try:
        tok_resp = requests.post(
            token_url,
            data=token_data,
            headers={"Accept": "application/json", "User-Agent": "ShadowTraderAI-MCPClient/3.0"},
            timeout=10.0
        )
        if tok_resp.status_code != 200:
            return _render_popup_html(
                False,
                "Token Exchange Failed",
                f"Robinhood token endpoint returned HTTP {tok_resp.status_code}: {tok_resp.text[:200]}"
            )
        tok_json = tok_resp.json()
        access_token = tok_json.get("access_token")
        refresh_token = tok_json.get("refresh_token")
        if not access_token:
            return _render_popup_html(
                False,
                "No Access Token Received",
                "Robinhood OAuth response did not include an access_token."
            )

        save_user_robinhood_credentials(
            user_id=user_id,
            mcp_url=mcp_url,
            mcp_token_enc=encrypt_kalshi_key(access_token.strip()),
            mcp_refresh_token_enc=encrypt_kalshi_key(refresh_token.strip()) if refresh_token else None,
            mcp_client_id=client_id,
            auth_mode="ROBINHOOD_MCP"
        )
        return _render_popup_html(
            True,
            "Robinhood Agentic MCP Connected!",
            "Your OAuth Bearer & Refresh tokens have been encrypted with AES-256 and linked to ShadowTrader AI. This window will close automatically."
        )
    except Exception as e:
        return _render_popup_html(
            False,
            "OAuth Token Exchange Error",
            f"Error communicating with Robinhood token server: {e}"
        )


@router.post("/config")
def save_user_investments_config(
    req: InvestmentsSettingsRequest,
    current_user: dict = Depends(get_current_user)
):
    """Saves user's investment universe configurations."""
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if updates:
        update_user_investments_config(current_user["id"], updates)
    return {"success": True, "message": "Investments settings updated."}
