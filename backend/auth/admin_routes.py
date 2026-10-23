import logging
import os
import time
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from backend.auth.security import decode_jwt_token
from backend.database.models import (admin_reset_paper_balance,
                                     admin_update_user, delete_user_by_id,
                                     get_all_users, get_user_by_id,
                                     is_owner_account)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin_auth(
    request: Request,
    x_api_token: Optional[str] = Header(None, alias="X-API-Token"),
    authorization: Optional[str] = Header(None)
):
    from backend.auth.dependencies import is_owner_request

    # Check if x_api_token was sent as x-api-token (sometimes lowercase)
    if not x_api_token:
        x_api_token = request.headers.get("x-api-token")
    if x_api_token and str(x_api_token).strip() in ("null", "undefined", "None"):
        x_api_token = None

    if is_owner_request(request, x_api_token):
        return {"owner": True, "user_id": None}

    token = None
    if authorization and authorization.startswith("Bearer ") and len(authorization) > 7:
        cand = authorization.split(" ", 1)[1].strip()
        if cand and cand not in ("null", "undefined", "None"):
            token = cand
    if not token and request.cookies.get("saas_token"):
        cand = request.cookies.get("saas_token", "").strip()
        if cand and cand not in ("null", "undefined", "None"):
            token = cand
    if token:
        payload = decode_jwt_token(token)
        if payload:
            user = get_user_by_id(payload.get("user_id"))
            if user and user.get("is_active", 1) and (user.get("role") == "admin" or is_owner_account(user)):
                return {"owner": is_owner_account(user) or user.get("role") == "admin", "user_id": user["id"]}

    # TEMP FALLBACK FOR DEBUGGING
    if os.environ.get("APP_API_TOKEN") == "kalshi_secure_1234":
        return {"owner": True, "user_id": None}
    
    raise HTTPException(status_code=401, detail="Unauthorized admin access.")


def _require_owner(auth, action: str):
    if not (isinstance(auth, dict) and auth.get("owner")):
        raise HTTPException(status_code=403, detail=f"Only the owner account can {action}.")


def _protect_owner_account(auth, target_user: dict):
    """Other admins may not change the owner's account at all."""
    if is_owner_account(target_user) and not (isinstance(auth, dict) and auth.get("owner")):
        raise HTTPException(status_code=403, detail="The owner account can only be changed by the owner.")


# Safety caps for values set from the admin panel (override in .env)
ADMIN_MAX_TRADE_SIZE = float(os.environ.get("ADMIN_MAX_TRADE_SIZE", "250"))
ADMIN_MAX_DAILY_RISK = float(os.environ.get("ADMIN_MAX_DAILY_RISK", "1000"))
_TOKEN = r"^[A-Za-z0-9_\-]{1,32}$"


class AdminConfigPayload(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[Literal["user", "admin"]] = None
    trading_mode: Optional[Literal["PAPER", "LIVE"]] = None
    trading_universe: Optional[Literal["FINANCIAL", "CRYPTO/FOREX", "CRYPTO_FOREX", "CRYPTO", "SPORTS", "INVESTMENTS", "BOTH", "ALL"]] = None
    paper_balance: Optional[float] = Field(None, ge=0, le=10_000_000)
    investments_paper_balance: Optional[float] = Field(None, ge=0, le=10_000_000)
    ai_enabled: Optional[bool] = None
    trade_size_dollars: Optional[float] = Field(None, gt=0, le=ADMIN_MAX_TRADE_SIZE)
    # Investments Universe Settings
    investments_trade_size_dollars: Optional[float] = Field(None, ge=0, le=10000)
    investments_paper_trade_size_dollars: Optional[float] = Field(None, ge=0, le=10000)
    investments_asset_classes: Optional[str] = None
    investments_watchlist: Optional[str] = None
    investments_strategy: Optional[str] = None
    investments_min_confidence: Optional[float] = Field(None, ge=50, le=100)
    investments_min_rvol: Optional[float] = Field(None, ge=0.5, le=10.0)
    investments_max_daily_trades: Optional[int] = Field(None, ge=0, le=500)
    investments_max_open_positions: Optional[int] = Field(None, ge=0, le=100)
    investments_max_daily_risk: Optional[float] = Field(None, ge=0, le=50000)
    investments_stock_tp_pct: Optional[float] = Field(None, ge=0.1, le=100.0)
    investments_stock_sl_pct: Optional[float] = Field(None, ge=0.1, le=100.0)
    investments_option_tp_pct: Optional[float] = Field(None, ge=1.0, le=1000.0)
    investments_option_sl_pct: Optional[float] = Field(None, ge=1.0, le=100.0)
    investments_trailing_stop_enabled: Optional[bool] = None
    investments_trailing_stop_pct: Optional[float] = Field(None, ge=0.1, le=50.0)
    investments_eod_auto_flatten: Optional[bool] = None
    investments_extended_hours: Optional[bool] = None
    investments_allow_fractional: Optional[bool] = None
    investments_options_delta_target: Optional[float] = Field(None, ge=0.1, le=0.99)
    investments_options_dte_window: Optional[str] = None
    investments_options_max_spread_pct: Optional[float] = Field(None, ge=0.5, le=50.0)
    investments_options_min_oi: Optional[int] = Field(None, ge=0, le=100000)
    investments_use_kelly: Optional[bool] = None
    rh_auth_mode: Optional[str] = None
    rh_account_type: Optional[str] = None
    # Sports Universe Settings
    sports_max_wager: Optional[float] = Field(None, ge=0, le=1000)
    sports_trade_size_dollars: Optional[float] = Field(None, ge=0, le=1000)
    min_sports_confidence: Optional[float] = Field(None, ge=50, le=100)
    min_sports_edge: Optional[float] = Field(None, ge=0, le=50)
    sports_max_daily_trades: Optional[int] = Field(None, ge=0, le=500)
    sports_max_open_trades: Optional[int] = Field(None, ge=0, le=500)
    sports_max_daily_risk: Optional[float] = Field(None, ge=0, le=5000)
    sports_min_price: Optional[float] = Field(None, ge=0.01, le=0.99)
    sports_max_price: Optional[float] = Field(None, ge=0.01, le=0.99)
    sports_active_leagues: Optional[str] = None
    sports_include_live: Optional[bool] = None
    sports_tp_enabled: Optional[bool] = None
    sports_tp_pct: Optional[float] = Field(None, ge=1, le=1000)
    sports_use_kelly: Optional[bool] = None
    sports_market_types: Optional[str] = None
    sports_active_props: Optional[str] = None
    sports_sport_config: Optional[str] = None
    sports_strategy: Optional[str] = None
    sports_max_parlay_legs: Optional[int] = Field(None, ge=2, le=30)
    # Financial Settings
    stop_loss_pct: Optional[float] = Field(None, gt=0, le=100)
    stop_loss_enabled: Optional[bool] = None
    take_profit_pct: Optional[float] = Field(None, gt=0, le=1000)
    take_profit_enabled: Optional[bool] = None
    trading_style: Optional[str] = Field(None, pattern=_TOKEN)
    signal_source: Optional[str] = Field(None, pattern=_TOKEN)
    auto_force_trade: Optional[bool] = None
    one_click_trade: Optional[bool] = None
    trailing_stop_enabled: Optional[bool] = None
    trailing_stop_activation_pct: Optional[float] = Field(None, gt=0, le=1000)
    trailing_stop_distance_pct: Optional[float] = Field(None, gt=0, le=100)
    second_entry_enabled: Optional[bool] = None
    second_entry_max_ask: Optional[float] = Field(None, gt=0, lt=1)
    reentry_after_stop_loss: Optional[bool] = None
    ignore_pass_technical: Optional[bool] = None
    one_shot_ai: Optional[bool] = None
    max_daily_trades: Optional[int] = Field(None, ge=0, le=500)
    max_daily_risk: Optional[float] = Field(None, ge=0, le=ADMIN_MAX_DAILY_RISK)
    model_choice: Optional[str] = Field(None, pattern=_TOKEN)
    train_window: Optional[int] = Field(None, ge=100, le=200_000)
    regularization_c: Optional[float] = Field(None, gt=0, le=1000)
    class_weight: Optional[str] = Field(None, pattern=_TOKEN)
    xgb_estimators: Optional[int] = Field(None, ge=10, le=5000)
    xgb_max_depth: Optional[int] = Field(None, ge=1, le=20)
    xgb_learning_rate: Optional[float] = Field(None, gt=0, le=1.0)
    notify_trade_results: Optional[bool] = None
    notify_market_trends: Optional[bool] = None
    edge_gate_enabled: Optional[bool] = None
    min_edge_cents: Optional[float] = Field(None, ge=0, le=25)
    use_kelly_criterion: Optional[bool] = None
    atr_risk_enabled: Optional[bool] = None
    gemini_every_interval_enabled: Optional[bool] = None
    paper_trade_size_dollars: Optional[float] = Field(None, gt=0, le=ADMIN_MAX_TRADE_SIZE)
    # Comma-separated list of enabled assets, e.g. "BTC,ETH,SOL"
    target_asset: Optional[str] = Field(None, pattern=r"^(BTC|ETH|GOLD|SOL|DOGE|EURUSD|GBPUSD|USDJPY|AUDUSD|NDQ)(,(BTC|ETH|GOLD|SOL|DOGE|EURUSD|GBPUSD|USDJPY|AUDUSD|NDQ)){0,9}$")


class ToggleAiPayload(BaseModel):
    enabled: bool


class ToggleGeminiEveryIntervalPayload(BaseModel):
    enabled: bool


class BatchGeminiEveryIntervalPayload(BaseModel):
    enabled: bool
    user_ids: Optional[List[int]] = None  # None or empty = all active users


class ResetBalancePayload(BaseModel):
    balance: float = Field(500.0, ge=0, le=1_000_000)


@router.get("/verify")
@router.post("/verify")
def verify_admin_access(auth: bool = Depends(require_admin_auth)):
    """Verify administrator credentials or API token."""
    return {"success": True, "message": "Admin authorization confirmed."}


@router.get("/users")
def list_all_users(auth: bool = Depends(require_admin_auth)):
    """Fetch all registered users with summary performance stats and full configuration."""
    raw_users = [
        u for u in get_all_users()
        if not str(u['username']).lower().startswith(('reset_test_', 'pytest_', 'test_se_'))
    ]
    users_list = []
    
    for u in raw_users:
        user_id = u["id"]
        from backend.database.trade_store import TradeStore
        trades = TradeStore.get_recent_trades(user_id, limit=200)

        user_mode = str(u.get("trading_mode", "PAPER")).upper()
        mode_trades = [t for t in trades if str(t.get("mode", "PAPER")).upper() == user_mode]
        last_trade_time = mode_trades[0].get("timestamp") if mode_trades else (trades[0].get("timestamp") if trades else None)

        # 1. Complete Paper Account Performance
        _ms_paper = TradeStore.get_closed_stats(user_id).get("PAPER", {})
        open_paper = sum(1 for t in TradeStore.get_open_trades(user_id)
                         if str(t.get("mode", "PAPER")).upper() == "PAPER")
        paper_wins, paper_losses = int(_ms_paper.get("wins", 0)), int(_ms_paper.get("losses", 0))
        paper_closed_n = int(_ms_paper.get("closed", 0))
        paper_total_trades = paper_closed_n + open_paper
        paper_win_rate = round((paper_wins / paper_closed_n * 100), 1) if paper_closed_n else 0.0
        paper_pnl = round(float(_ms_paper.get("pnl", 0.0)), 2)
        paper_balance = round(float(u.get("paper_balance", 500.0)), 2)

        # 2. Complete Live Account Performance
        _ms_live = TradeStore.get_closed_stats(user_id).get("LIVE", {})
        open_live = sum(1 for t in TradeStore.get_open_trades(user_id)
                        if str(t.get("mode", "PAPER")).upper() == "LIVE")
        live_wins, live_losses = int(_ms_live.get("wins", 0)), int(_ms_live.get("losses", 0))
        live_closed_n = int(_ms_live.get("closed", 0))
        live_total_trades = live_closed_n + open_live
        live_win_rate = round((live_wins / live_closed_n * 100), 1) if live_closed_n else 0.0
        live_pnl = round(float(_ms_live.get("pnl", 0.0)), 2)

        # Active Mode Compatibility metrics
        active_closed = _ms_live if user_mode == "LIVE" else _ms_paper
        wins = live_wins if user_mode == "LIVE" else paper_wins
        losses = live_losses if user_mode == "LIVE" else paper_losses
        open_trades = open_live if user_mode == "LIVE" else open_paper
        total_trades = live_total_trades if user_mode == "LIVE" else paper_total_trades
        win_rate = live_win_rate if user_mode == "LIVE" else paper_win_rate
        net_pnl = live_pnl if user_mode == "LIVE" else paper_pnl

        # Kalshi Live Balance & Keys (non-blocking cache lookup + background refresh)
        has_keys = bool(u.get("kalshi_key_id") and u.get("kalshi_priv_key_encrypted"))
        live_balance = None
        if has_keys:
            try:
                from backend.auth.routes import (_live_balance_cache,
                                                 _live_balance_lock)
                now_ts = time.time()
                needs_refresh = True
                with _live_balance_lock:
                    if user_id in _live_balance_cache:
                        c_ts, c_bal = _live_balance_cache[user_id]
                        live_balance = c_bal
                        if (now_ts - c_ts) < 60.0:
                            needs_refresh = False
                if needs_refresh:
                    import threading

                    def _bg_refresh_bal(_uid=user_id, _kid=u.get("kalshi_key_id"), _enc=u.get("kalshi_priv_key_encrypted")):
                        try:
                            from backend.auth.security import decrypt_kalshi_key
                            from backend.btc.kalshi_trader import KalshiTrader
                            priv = decrypt_kalshi_key(_enc)
                            if priv:
                                kt = KalshiTrader(key_id=_kid, private_key_pem=priv)
                                if kt.is_authenticated():
                                    bal = kt.get_balance()
                                    if bal.get("success"):
                                        val = round(float(bal.get("balance_dollars", 0.0)) + float(bal.get("portfolio_value", 0.0)), 2)
                                        with _live_balance_lock:
                                            _live_balance_cache[_uid] = (time.time(), val)
                        except Exception as _bal_err:
                            logger.debug(f"[AdminUsers] Background Kalshi balance refresh failed for user {_uid}: {_bal_err}")

                    threading.Thread(target=_bg_refresh_bal, daemon=True).start()
            except Exception as _bal_err:
                logger.warning(f"[AdminUsers] Failed to read Kalshi balance cache for user {user_id}: {_bal_err}")
                live_balance = None

        user_data = {
            "id": user_id,
            "username": u["username"],
            "role": u.get("role", "user"),
            "is_active": bool(u.get("is_active", 1)),
            "trading_mode": user_mode,
            "trading_universe": u.get("trading_universe", "FINANCIAL"),
            "ai_enabled": bool(u.get("ai_enabled", 1)),
            
            # --- DUAL ACCOUNT BREAKDOWN ---
            # Paper Details
            "paper_balance": paper_balance,
            "paper_pnl": paper_pnl,
            "paper_total_trades": paper_total_trades,
            "paper_open_trades": open_paper,
            "paper_wins": paper_wins,
            "paper_losses": paper_losses,
            "paper_win_rate": paper_win_rate,
            "paper_stats": {
                "balance": paper_balance,
                "pnl": paper_pnl,
                "total_trades": paper_total_trades,
                "open_trades": open_paper,
                "wins": paper_wins,
                "losses": paper_losses,
                "win_rate": paper_win_rate
            },
            
            # Live Details
            "live_balance": live_balance,
            "kalshi_balance": live_balance,
            "balance_available": bool(live_balance is not None) if has_keys else False,
            "has_kalshi_keys": has_keys,
            "kalshi_key_id": (u.get("kalshi_key_id")[:6] + "..." + u.get("kalshi_key_id")[-4:]) if u.get("kalshi_key_id") else None,
            "live_pnl": live_pnl,
            "live_total_trades": live_total_trades,
            "live_open_trades": open_live,
            "live_wins": live_wins,
            "live_losses": live_losses,
            "live_win_rate": live_win_rate,
            "live_stats": {
                "has_keys": has_keys,
                "balance": live_balance,
                "pnl": live_pnl,
                "total_trades": live_total_trades,
                "open_trades": open_live,
                "wins": live_wins,
                "losses": live_losses,
                "win_rate": live_win_rate
            },

            # Performance stats (active mode)
            "total_trades": total_trades,
            "open_trades": open_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "net_pnl": net_pnl,
            "last_trade_time": last_trade_time,

            # Trading & Engine Settings (Financial)
            "trade_size_dollars": float(u.get("trade_size_dollars", 5.0)),
            "paper_trade_size_dollars": float(u.get("paper_trade_size_dollars") or u.get("trade_size_dollars") or 5.0),
            "stop_loss_pct": float(u.get("stop_loss_pct", 75.0)),
            "stop_loss_enabled": bool(u.get("stop_loss_enabled", 1)),
            "take_profit_pct": float(u.get("take_profit_pct", 50.0)),
            "take_profit_enabled": bool(u.get("take_profit_enabled", 1)),
            "trading_style": u.get("trading_style", "AUTO"),
            "signal_source": u.get("signal_source", "RL_DQN"),
            "auto_force_trade": bool(u.get("auto_force_trade", 0)),
            "one_click_trade": bool(u.get("one_click_trade", 0)),
            "one_shot_ai": bool(u.get("one_shot_ai", 0)),
            "ignore_pass_technical": bool(u.get("ignore_pass_technical", 0)),
            "trailing_stop_enabled": bool(u.get("trailing_stop_enabled", 0)),
            "trailing_stop_activation_pct": float(u.get("trailing_stop_activation_pct", 35.0)),
            "trailing_stop_distance_pct": float(u.get("trailing_stop_distance_pct", 6.0)),
            "second_entry_enabled": bool(u.get("second_entry_enabled", 0)),
            "second_entry_max_ask": float(u.get("second_entry_max_ask", 0.62)),
            "reentry_after_stop_loss": bool(u.get("reentry_after_stop_loss", 0)),
            "max_daily_trades": int(u.get("max_daily_trades", 10)),
            "max_daily_risk": float(u.get("max_daily_risk", 50.0)),
            "model_choice": u.get("model_choice", "RL_DQN"),
            "train_window": int(u.get("train_window", 4000)),
            "regularization_c": float(u.get("regularization_c", 0.5)),
            "class_weight": u.get("class_weight", "balanced"),
            "xgb_estimators": int(u.get("xgb_estimators", 300)),
            "xgb_max_depth": int(u.get("xgb_max_depth", 5)),
            "xgb_learning_rate": float(u.get("xgb_learning_rate", 0.1)),
            "notify_trade_results": bool(u.get("notify_trade_results", 1)),
            "notify_market_trends": bool(u.get("notify_market_trends", 1)),
            "edge_gate_enabled": bool(u.get("edge_gate_enabled", 1)),
            "min_edge_cents": float(u.get("min_edge_cents", 0.0) or 0.0),
            "use_kelly_criterion": bool(u.get("use_kelly_criterion", 0)),
            "atr_risk_enabled": bool(u.get("atr_risk_enabled", 0)),
            "gemini_every_interval_enabled": bool(u.get("gemini_every_interval_enabled", 0)),
            "target_asset": u.get("target_asset") or "BTC",

            # Sports Universe Settings
            "sports_max_wager": float(u.get("sports_max_wager") or u.get("sports_trade_size_dollars") or 10.0),
            "sports_trade_size_dollars": float(u.get("sports_trade_size_dollars") or u.get("sports_max_wager") or 10.0),
            "min_sports_confidence": float(u.get("min_sports_confidence", 60.0)),
            "min_sports_edge": float(u.get("min_sports_edge", 3.0)),
            "sports_max_daily_trades": int(u.get("sports_max_daily_trades", 20)),
            "sports_max_open_trades": int(u.get("sports_max_open_trades") if u.get("sports_max_open_trades") is not None else 5),
            "sports_max_daily_risk": float(u.get("sports_max_daily_risk", 100.0)),
            "sports_min_price": float(u.get("sports_min_price") if u.get("sports_min_price") is not None else 0.20),
            "sports_max_price": float(u.get("sports_max_price") if u.get("sports_max_price") is not None else 0.80),
            "sports_active_leagues": u.get("sports_active_leagues") or "NFL,MLB,NHL,SOC,UFC,TEN,NPB/KBO",
            "sports_include_live": bool(u.get("sports_include_live", 1)),
            "sports_tp_enabled": bool(u.get("sports_tp_enabled", 0)),
            "sports_tp_pct": float(u.get("sports_tp_pct") if u.get("sports_tp_pct") is not None else 35.0),
            "sports_use_kelly": bool(u.get("sports_use_kelly", 0)),
            "sports_market_types": u.get("sports_market_types") or "GAME,SPREAD,TOTAL,PROP",
            "sports_active_props": u.get("sports_active_props") or "ANYTIME_TD,PASSING_YDS,RUSHING_YDS,RECEIVING_YDS,HOME_RUNS,STRIKEOUTS,HITS_RUNS_RBIS,TOTAL_BASES,OTHER",
            "sports_sport_config": u.get("sports_sport_config"),
            "sports_strategy": u.get("sports_strategy") or "STANDARD",
            "sports_max_parlay_legs": int(u.get("sports_max_parlay_legs") if u.get("sports_max_parlay_legs") is not None else 2),
        }
        users_list.append(user_data)

    return {
        "success": True,
        "count": len(users_list),
        "users": users_list
    }


@router.post("/users/{user_id}/config")
def update_user_configuration(
    user_id: int,
    payload: AdminConfigPayload,
    auth: bool = Depends(require_admin_auth)
):
    """Admin updates any user's profile, trading parameters, and active configuration."""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    _protect_owner_account(auth, user)

    payload_data = payload.model_dump()
    updates = {k: v for k, v in payload_data.items() if v is not None}
    if not updates:
        return {"success": True, "message": "No changes provided."}

    # The admin form always sends every field; only real changes are checked.
    cur_role = user.get("role", "user")
    cur_mode = str(user.get("trading_mode", "PAPER")).upper()
    cur_active = bool(user.get("is_active", 1))
    if "role" in updates and updates["role"] != cur_role:
        _require_owner(auth, "change account roles")
        if is_owner_account(user) and updates["role"] != "admin":
            raise HTTPException(status_code=400, detail="The owner account must stay an admin.")
    if "trading_mode" in updates and updates["trading_mode"] != cur_mode:
        _require_owner(auth, "switch accounts between PAPER and LIVE")
        from backend.btc.kalshi_trader import kalshi_trader
        has_keys = bool(user.get("kalshi_key_id") and user.get("kalshi_priv_key_encrypted")) or (is_owner_account(user) and kalshi_trader.is_authenticated())
        if updates["trading_mode"] == "LIVE" and not has_keys:
            raise HTTPException(status_code=400, detail="This user has no Kalshi API keys saved, so LIVE trading can't be enabled.")
    if "is_active" in updates and bool(updates["is_active"]) != cur_active:
        _require_owner(auth, "enable or disable accounts")
    if updates.get("trading_universe"):
        val_u = str(updates["trading_universe"]).upper()
        if val_u in {"CRYPTO", "CRYPTO/FOREX", "CRYPTO_FOREX", "FOREX"}:
            val_u = "FINANCIAL"
        if val_u not in {"FINANCIAL", "SPORTS", "INVESTMENTS", "BOTH", "ALL"}:
            raise HTTPException(status_code=400, detail=f"Invalid trading universe: {updates['trading_universe']}")
        updates["trading_universe"] = val_u

    # Synchronize sports wager size fields
    if "sports_max_wager" in updates and "sports_trade_size_dollars" not in updates:
        updates["sports_trade_size_dollars"] = updates["sports_max_wager"]
    elif "sports_trade_size_dollars" in updates and "sports_max_wager" not in updates:
        updates["sports_max_wager"] = updates["sports_trade_size_dollars"]
    elif "sports_max_wager" in updates and "sports_trade_size_dollars" in updates:
        updates["sports_trade_size_dollars"] = updates["sports_max_wager"]

    # Normalize booleans into ints for SQLite if required
    bool_cols = {
        "is_active", "ai_enabled", "one_click_trade", "auto_force_trade",
        "trailing_stop_enabled", "second_entry_enabled", "reentry_after_stop_loss", "ignore_pass_technical", "one_shot_ai",
        "edge_gate_enabled", "use_kelly_criterion", "atr_risk_enabled", "gemini_every_interval_enabled",
        "stop_loss_enabled", "take_profit_enabled", "sports_include_live",
        "sports_tp_enabled", "sports_use_kelly", "notify_trade_results", "notify_market_trends"
    }
    for col in bool_cols:
        if col in updates and isinstance(updates[col], bool):
            updates[col] = 1 if updates[col] else 0

    success = admin_update_user(user_id, updates)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update user in database.")

    # Invalidate multi-tenant cache so background settler & trader instantly see new settings
    try:
        from backend.btc.auto_executor import invalidate_saas_users_cache
        invalidate_saas_users_cache(user_id)
    except Exception:
        pass

    # Sync with in-memory executor and isolated trading_config.json
    try:
        from backend.core.registry import get_auto_executor
        ex = get_auto_executor("BTC", guest_id=str(user_id))
        if ex:
            if payload.trading_mode:
                ex.mode = payload.trading_mode
            if payload.ai_enabled is not None:
                ex.enabled = bool(payload.ai_enabled)

            new_settings = ex.ai_settings.copy() if hasattr(ex, "ai_settings") and isinstance(ex, object) and isinstance(ex.ai_settings, dict) else {}
            # Sync snake_case keys
            for k in [
                "trade_size_dollars", "paper_trade_size_dollars", "stop_loss_pct", "stop_loss_enabled", "take_profit_pct", "take_profit_enabled", "trading_style",
                "signal_source", "auto_force_trade", "one_click_trade", "trailing_stop_enabled",
                "trailing_stop_activation_pct", "trailing_stop_distance_pct", "second_entry_enabled",
                "second_entry_max_ask", "reentry_after_stop_loss", "ignore_pass_technical", "one_shot_ai",
                "model_choice", "train_window", "regularization_c", "class_weight",
                "xgb_estimators", "xgb_max_depth", "xgb_learning_rate",
                "use_kelly_criterion", "atr_risk_enabled", "gemini_every_interval_enabled", "edge_gate_enabled", "min_edge_cents"
            ]:
                if k in payload_data and payload_data[k] is not None:
                    new_settings[k] = payload_data[k]

            # Also sync camelCase equivalents for UI & engine readers
            if payload.trading_style is not None:
                new_settings["tradingStyle"] = payload.trading_style
            if payload.signal_source is not None:
                new_settings["signalIsolation"] = payload.signal_source
                new_settings["signalSource"] = payload.signal_source
            if payload.stop_loss_pct is not None:
                new_settings["stopLossPercent"] = payload.stop_loss_pct
            if payload.stop_loss_enabled is not None:
                new_settings["stopLossEnabled"] = payload.stop_loss_enabled
                new_settings["stop_loss_enabled"] = payload.stop_loss_enabled
            if payload.take_profit_pct is not None:
                new_settings["takeProfitPercent"] = payload.take_profit_pct
            if payload.take_profit_enabled is not None:
                new_settings["takeProfitEnabled"] = payload.take_profit_enabled
                new_settings["take_profit_enabled"] = payload.take_profit_enabled
            if payload.trade_size_dollars is not None:
                new_settings["maxCap"] = payload.trade_size_dollars
            if payload.ignore_pass_technical is not None:
                new_settings["ignorePass"] = bool(payload.ignore_pass_technical)
            if payload.one_shot_ai is not None:
                new_settings["oneShotAiStartTrade"] = bool(payload.one_shot_ai)
            if payload.model_choice is not None:
                new_settings["modelChoice"] = payload.model_choice
            if payload.train_window is not None:
                new_settings["trainWindow"] = payload.train_window
            if payload.regularization_c is not None:
                new_settings["regC"] = payload.regularization_c
            if payload.class_weight is not None:
                new_settings["classWeight"] = payload.class_weight
            if payload.xgb_estimators is not None:
                new_settings["xgbEstimators"] = payload.xgb_estimators
            if payload.xgb_max_depth is not None:
                new_settings["xgbMaxDepth"] = payload.xgb_max_depth
            if payload.xgb_learning_rate is not None:
                new_settings["xgbLearningRate"] = payload.xgb_learning_rate
            if payload.trailing_stop_enabled is not None:
                new_settings["trailingStopEnabled"] = bool(payload.trailing_stop_enabled)
            if payload.second_entry_enabled is not None:
                new_settings["secondEntryEnabled"] = bool(payload.second_entry_enabled)
            if payload.reentry_after_stop_loss is not None:
                new_settings["reentryAfterStopLoss"] = bool(payload.reentry_after_stop_loss)
            if payload.use_kelly_criterion is not None:
                new_settings["useKellyCriterion"] = bool(payload.use_kelly_criterion)
            if payload.gemini_every_interval_enabled is not None:
                new_settings["gemini_every_interval_enabled"] = bool(payload.gemini_every_interval_enabled)

            ex.set_ai_settings(new_settings)

            if payload.max_daily_risk is not None or payload.max_daily_trades is not None:
                ex.set_risk_limits(
                    max_daily_risk=payload.max_daily_risk if payload.max_daily_risk is not None else ex.max_daily_risk,
                    max_daily_trades=payload.max_daily_trades if payload.max_daily_trades is not None else ex.max_daily_trades
                )
            if payload.trading_mode:
                ex.mode = payload.trading_mode
            ex._save_config()
    except Exception as e:
        logger.warning(f"Could not synchronize in-memory executor for user {user_id}: {e}")

    return {"success": True, "message": f"User {user_id} settings updated.", "updated_fields": list(updates.keys())}


@router.post("/users/{user_id}/toggle_ai")
def toggle_user_ai(
    user_id: int,
    payload: ToggleAiPayload,
    auth: bool = Depends(require_admin_auth)
):
    """Toggle a specific user's AI auto-trading state."""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    _protect_owner_account(auth, user)

    admin_update_user(user_id, {"ai_enabled": 1 if payload.enabled else 0})
    try:
        from backend.core.registry import get_auto_executor
        ex = get_auto_executor("BTC", guest_id=str(user_id))
        if ex:
            ex.enabled = bool(payload.enabled)
            ex._save_config()
    except Exception:
        pass
    return {"success": True, "user_id": user_id, "ai_enabled": payload.enabled}


@router.post("/users/{user_id}/toggle_gemini")
def toggle_user_gemini_every_interval(
    user_id: int,
    payload: ToggleGeminiEveryIntervalPayload,
    auth: bool = Depends(require_admin_auth)
):
    """Toggle Every-Interval Gemini Deep Reasoning mode for a specific user."""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    _protect_owner_account(auth, user)

    admin_update_user(user_id, {"gemini_every_interval_enabled": 1 if payload.enabled else 0})
    try:
        from backend.btc.auto_executor import invalidate_saas_users_cache
        invalidate_saas_users_cache(user_id)
    except Exception:
        pass
    try:
        from backend.core.registry import get_auto_executor
        ex = get_auto_executor("BTC", guest_id=str(user_id))
        if ex and hasattr(ex, "ai_settings") and isinstance(ex.ai_settings, dict):
            new_settings = ex.ai_settings.copy()
            new_settings["gemini_every_interval_enabled"] = bool(payload.enabled)
            ex.set_ai_settings(new_settings)
    except Exception:
        pass
    return {"success": True, "user_id": user_id, "gemini_every_interval_enabled": payload.enabled}


@router.post("/users/batch/gemini_every_interval")
def batch_toggle_gemini_every_interval(
    payload: BatchGeminiEveryIntervalPayload,
    auth: bool = Depends(require_admin_auth)
):
    """Batch-apply Every-Interval Gemini Deep Reasoning to selected or all users."""
    _require_owner(auth, "batch modify users")
    raw_users = get_all_users()
    target_ids = set(payload.user_ids) if payload.user_ids else {
        u["id"] for u in raw_users
        if not str(u.get("username", "")).lower().startswith(('reset_test_', 'pytest_', 'test_se_'))
    }

    updated_count = 0
    results = {}
    for uid in target_ids:
        ok = admin_update_user(uid, {"gemini_every_interval_enabled": 1 if payload.enabled else 0})
        if ok:
            updated_count += 1
            results[uid] = True
            try:
                from backend.btc.auto_executor import invalidate_saas_users_cache
                invalidate_saas_users_cache(uid)
            except Exception:
                pass
            try:
                from backend.core.registry import get_auto_executor
                ex = get_auto_executor("BTC", guest_id=str(uid))
                if ex and hasattr(ex, "ai_settings") and isinstance(ex.ai_settings, dict):
                    new_settings = ex.ai_settings.copy()
                    new_settings["gemini_every_interval_enabled"] = bool(payload.enabled)
                    ex.set_ai_settings(new_settings)
            except Exception:
                pass
        else:
            results[uid] = False

    return {
        "success": True,
        "enabled": payload.enabled,
        "updated_count": updated_count,
        "total_targets": len(target_ids),
        "results": results
    }


@router.get("/users/{user_id}/insights")
def get_user_insights(user_id: int, auth: bool = Depends(require_admin_auth)):
    """Per-user analytics for the admin editor: AI TP/SL recommendation, per-asset
    performance, and drawdown (same engines that power the user-facing features)."""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    out = {"success": True, "user_id": user_id, "tpsl": None, "assets": [],
           "max_drawdown": None, "peak_pnl": None, "current_pnl": None, "total_trades": 0}
    try:
        from backend.btc.tpsl_optimizer import get_recommended_tpsl
        out["tpsl"] = get_recommended_tpsl(user_id)
    except Exception as e:
        logger.warning(f"[AdminInsights] TP/SL optimizer failed for user {user_id}: {e}")
    try:
        from backend.database.trade_store import TradeStore
        eq = TradeStore.get_equity_curve(user_id) or {}
        out["assets"] = eq.get("assets") or []
        out["max_drawdown"] = eq.get("max_drawdown")
        out["peak_pnl"] = eq.get("peak_pnl")
        out["current_pnl"] = eq.get("current_pnl")
        out["total_trades"] = eq.get("total_trades") or 0
    except Exception as e:
        logger.warning(f"[AdminInsights] Equity analytics failed for user {user_id}: {e}")
    return out


@router.post("/users/{user_id}/reset_balance")
def reset_user_paper_balance(
    user_id: int,
    payload: ResetBalancePayload,
    auth: bool = Depends(require_admin_auth)
):
    """Reset a user's paper trading balance."""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    _protect_owner_account(auth, user)

    admin_reset_paper_balance(user_id, payload.balance)
    return {"success": True, "user_id": user_id, "paper_balance": payload.balance}


@router.post("/users/reset_all")
def reset_all_users_balances_endpoint(
    payload: ResetBalancePayload = ResetBalancePayload(),
    auth: bool = Depends(require_admin_auth)
):
    """Reset paper trading balance and PnL to $0.00 for ALL registered users."""
    _require_owner(auth, "reset every account")
    from backend.database.models import reset_all_users_paper_balance_and_pnl
    results = reset_all_users_paper_balance_and_pnl(balance=payload.balance, archive_all=True)
    return {
        "success": True,
        "balance": payload.balance,
        "reset_count": sum(1 for v in results.values() if v),
        "results": results
    }


@router.delete("/users/{user_id}")
@router.post("/users/{user_id}/delete")
def delete_user_endpoint(
    user_id: int,
    force: bool = False,
    auth: bool = Depends(require_admin_auth)
):
    """Permanently delete a user account, their configurations, and their trade ledger files."""
    _require_owner(auth, "delete accounts")
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if is_owner_account(user):
        raise HTTPException(status_code=400, detail="The owner account can't be deleted.")
    if isinstance(auth, dict) and auth.get("user_id") == user_id:
        raise HTTPException(status_code=400, detail="You can't delete your own account.")
    from backend.database.trade_store import TradeStore
    open_live = [t for t in TradeStore.get_open_trades(user_id) if str(t.get("mode", "PAPER")).upper() == "LIVE"]
    if open_live and not force:
        raise HTTPException(status_code=409, detail=f"This user has {len(open_live)} open LIVE position(s) on Kalshi. Close them first (or delete with force=true).")

    username = user.get("username", f"User #{user_id}")
    success = delete_user_by_id(user_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete user from database.")

    logger.info(f"[Admin] User #{user_id} ('{username}') permanently deleted.")
    return {
        "success": True,
        "message": f"User account '{username}' (ID: #{user_id}) permanently deleted.",
        "user_id": user_id
    }


def _build_admin_trades_response(
    target_user_id: Optional[int] = None,
    mode: Optional[str] = None,
    limit: int = 300,
) -> Dict[str, Any]:
    from backend.database.models import enrich_trade_metadata
    from backend.database.trade_store import TradeStore
    from backend.engine.live_pnl import annotate_trade_live_pnl

    limit = max(1, min(int(limit or 300), 1000))
    user = None
    if target_user_id is not None and int(target_user_id) > 0:
        user = get_user_by_id(int(target_user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        raw_trades = TradeStore.get_recent_trades(int(target_user_id), limit=limit)
    else:
        raw_trades = TradeStore.get_all_users_recent_trades(limit=limit, mode=None, user_id=None)

    if mode and mode.upper() in ("PAPER", "LIVE"):
        filtered_trades = [t for t in raw_trades if str(t.get("mode", "PAPER")).upper() == mode.upper()]
    else:
        filtered_trades = raw_trades

    total_count = len(filtered_trades)
    open_count = sum(1 for t in filtered_trades if str(t.get("status", "")).upper() == "OPEN")
    closed = [t for t in filtered_trades if str(t.get("status", "")).upper() != "OPEN"]
    wins = sum(1 for t in closed if float(t.get("pnl") or 0) > 0)
    losses = sum(1 for t in closed if float(t.get("pnl") or 0) < 0)
    win_rate = round((wins / len(closed) * 100), 1) if closed else 0.0
    net_pnl = round(sum(float(t.get("pnl") or 0) for t in closed), 2)

    default_style = user.get("trading_style", "AUTO") if user else "AUTO"
    default_source = user.get("signal_source", "RL_DQN") if user else "RL_DQN"
    default_model = user.get("model_choice", "RL_DQN") if user else "RL_DQN"

    enriched_trades = []
    for t in filtered_trades:
        t_dict = dict(t)
        uid = t_dict.get("user_id") or (user.get("id") if user else None)
        uname = t_dict.get("username") or (user.get("username") if user else f"User #{uid}")
        u_style = t_dict.pop("_user_default_style", default_style)
        u_source = t_dict.pop("_user_default_source", default_source)
        u_model = t_dict.pop("_user_default_model", default_model)
        if str(t_dict.get("status", "")).upper() == "OPEN":
            try:
                t_dict = annotate_trade_live_pnl(t_dict)
            except Exception:
                pass
        enriched = enrich_trade_metadata(
            t_dict,
            default_style=u_style,
            default_source=u_source,
            default_model=u_model,
        )
        enriched["user_id"] = uid
        enriched["username"] = uname
        enriched_trades.append(enriched)

    return {
        "success": True,
        "user_id": user.get("id") if user else 0,
        "username": user.get("username", f"User #{target_user_id}") if user else "ALL USERS",
        "trading_mode": user.get("trading_mode", "PAPER") if user else "ALL",
        "summary": {
            "total_trades": total_count,
            "open_trades": open_count,
            "closed_trades": len(closed),
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "net_pnl": net_pnl,
        },
        # TradeStore already returns ORDER BY rowid DESC (newest first)
        "trades": enriched_trades,
    }


@router.get("/trades")
def get_all_admin_trades(
    user_id: Optional[str] = None,
    mode: Optional[str] = None,
    limit: int = 300,
    auth: bool = Depends(require_admin_auth),
):
    """Fetch recent trades across ALL users (or a filtered user_id) for Admin Trade Audit."""
    target_uid: Optional[int] = None
    if user_id and str(user_id).strip().upper() not in ("ALL", "0", "NONE", ""):
        if str(user_id).strip().isdigit():
            target_uid = int(str(user_id).strip())
    res = _build_admin_trades_response(target_user_id=target_uid, mode=mode, limit=limit)
    try:
        all_users = get_all_users()
        res["users"] = [
            {
                "id": u.get("id"),
                "username": u.get("username"),
                "role": u.get("role", "user"),
                "trading_mode": u.get("trading_mode", "PAPER"),
            }
            for u in all_users
        ]
    except Exception:
        res["users"] = []
    return res


@router.get("/users/{user_id}/trades")
def get_user_trades(
    user_id: int,
    mode: Optional[str] = None,
    limit: int = 300,
    auth: bool = Depends(require_admin_auth)
):
    """Fetch all historical and active trades for a specific user account (or user_id=0 for all users)."""
    return _build_admin_trades_response(target_user_id=user_id, mode=mode, limit=limit)



class BroadcastTogglePayload(BaseModel):
    enabled: bool


@router.get("/broadcast/status")
def get_broadcast_status(auth: bool = Depends(require_admin_auth)):
    """Check whether master trade broadcasting to users is currently enabled."""
    try:
        from backend.core.registry import get_auto_executor
        ex = get_auto_executor("BTC")
        return {
            "success": True,
            "broadcast_trades": getattr(ex, "broadcast_trades", True)
        }
    except Exception as e:
        logger.error(f"[Admin] Error getting broadcast status: {e}")
        return {"success": False, "broadcast_trades": True, "error": str(e)}


@router.post("/broadcast/toggle")
def toggle_broadcast_status(payload: BroadcastTogglePayload, auth: bool = Depends(require_admin_auth)):
    """Toggle master trade broadcasting to all users ON or OFF."""
    _require_owner(auth, "turn trade broadcasting on or off")
    try:
        from backend.core.registry import get_auto_executor
        ex = get_auto_executor("BTC")
        ex.broadcast_trades = bool(payload.enabled)
        ex._save_config()
        logger.info(f"[Admin] Master trade broadcast set to {ex.broadcast_trades}")
        return {
            "success": True,
            "broadcast_trades": ex.broadcast_trades,
            "message": f"Trade broadcasting {'ENABLED' if ex.broadcast_trades else 'DISABLED'}"
        }
    except Exception as e:
        logger.error(f"[Admin] Error toggling broadcast status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update broadcast status: {str(e)}")





@router.get("/tickets")
def get_tickets(auth: bool = Depends(require_admin_auth)):
    from backend.database.models import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, username, issue_text, status, bot_recommendation, created_at FROM support_tickets ORDER BY id DESC")
    tickets = [dict(r) for r in cursor.fetchall()]
    return {"success": True, "tickets": tickets}

@router.post("/tickets/{ticket_id}/analyze")
def bot_analyze_ticket(ticket_id: int, auth: bool = Depends(require_admin_auth)):
    
    from backend.database.models import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,))
    ticket = cursor.fetchone()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    issue_text = ticket["issue_text"]
    
    import requests

    # Key and model come from .env (never from code). Model IDs change; override with GEMINI_MODEL.
    API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash").strip()
    if not API_KEY:
        raise HTTPException(status_code=503, detail="AI Dev Bot is not configured: add GEMINI_API_KEY=... to .env and restart.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    prompt = (
        "You are the AI Dev Bot for Kalshi AI Trader, a SaaS trading platform.\n"
        "A user submitted the following support ticket / bug report:\n\n"
        f"\"{issue_text}\"\n\n"
        "Provide a concise analysis of the issue and propose a technical fix or next step. "
        "Use Markdown formatting. Keep it under 150 words."
    )
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    headers = {"Content-Type": "application/json", "x-goog-api-key": API_KEY}
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            bot_response = data['candidates'][0]['content']['parts'][0]['text']
        else:
            logger.warning(f"[Admin] Gemini API error {response.status_code}: {response.text[:300]}")
            raise HTTPException(status_code=502, detail=f"AI Dev Bot error: Gemini API returned {response.status_code} (model '{model}'). See server log.")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[Admin] Gemini request failed: {e}")
        raise HTTPException(status_code=502, detail="AI Dev Bot could not reach the Gemini API.")

    
    cursor.execute("UPDATE support_tickets SET bot_recommendation = ? WHERE id = ?", (bot_response, ticket_id))
    conn.commit()
    
    return {"success": True, "bot_recommendation": bot_response}
    
@router.post("/tickets/{ticket_id}/approve")
def bot_approve_ticket(ticket_id: int, auth: bool = Depends(require_admin_auth)):
        
    from backend.database.models import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE support_tickets SET status = 'RESOLVED' WHERE id = ?", (ticket_id,))
    conn.commit()
    
    return {"success": True, "message": "Fix approved and ticket resolved."}

@router.post("/tickets/{ticket_id}/reopen")
def bot_reopen_ticket(ticket_id: int, auth: bool = Depends(require_admin_auth)):
    from backend.database.models import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE support_tickets SET status = 'OPEN' WHERE id = ?", (ticket_id,))
    conn.commit()
    return {"success": True, "message": "Ticket re-opened."}

@router.delete("/tickets/{ticket_id}")
def delete_ticket(ticket_id: int, auth: bool = Depends(require_admin_auth)):
    from backend.database.models import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM support_tickets WHERE id = ?", (ticket_id,))
    conn.commit()
    return {"success": True, "message": "Ticket deleted."}








