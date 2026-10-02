import logging
import os
import time
from typing import Literal, Optional

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
        
    if is_owner_request(request, x_api_token):
        return {"owner": True, "user_id": None}

    token = None
    if authorization and authorization.startswith("Bearer ") and len(authorization) > 7:
        token = authorization.split(" ")[1].strip()
    if not token and request.cookies.get("saas_token"):
        token = request.cookies.get("saas_token")
    if token:
        payload = decode_jwt_token(token)
        if payload:
            user = get_user_by_id(payload.get("user_id"))
            if user and user.get("role") == "admin" and user.get("is_active"):
                return {"owner": is_owner_account(user), "user_id": user["id"]}

    # TEMP FALLBACK FOR DEBUGGING
    # return {"owner": True, "user_id": None}
    
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
    paper_balance: Optional[float] = Field(None, ge=0, le=1_000_000)
    ai_enabled: Optional[bool] = None
    trade_size_dollars: Optional[float] = Field(None, gt=0, le=ADMIN_MAX_TRADE_SIZE)
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
    edge_gate_enabled: Optional[bool] = None
    min_edge_cents: Optional[float] = Field(None, ge=0, le=25)
    use_kelly_criterion: Optional[bool] = None


class ToggleAiPayload(BaseModel):
    enabled: bool


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

        user_mode = u.get("trading_mode", "PAPER")
        mode_trades = [t for t in trades if t.get("mode", "PAPER") == user_mode]
        # All-time stats for the user's mode (not limited to the last 200 trades)
        _ms = TradeStore.get_closed_stats(user_id).get(str(user_mode).upper(), {})
        open_trades = sum(1 for t in TradeStore.get_open_trades(user_id)
                          if str(t.get("mode", "PAPER")).upper() == str(user_mode).upper())
        wins, losses = int(_ms.get("wins", 0)), int(_ms.get("losses", 0))
        _closed_n = int(_ms.get("closed", 0))
        total_trades = _closed_n + open_trades
        win_rate = round((wins / _closed_n * 100), 1) if _closed_n else 0.0
        net_pnl = round(float(_ms.get("pnl", 0.0)), 2)
        last_trade_time = mode_trades[-1].get("timestamp") if mode_trades else (trades[-1].get("timestamp") if trades else None)

        user_mode = u.get("trading_mode", "PAPER")
        has_keys = bool(u.get("kalshi_key_id") and u.get("kalshi_priv_key_encrypted"))
        live_balance = None
        if has_keys:
            try:
                from backend.auth.routes import (_live_balance_cache,
                                                 _live_balance_lock)
                now_ts = time.time()
                with _live_balance_lock:
                    if user_id in _live_balance_cache:
                        c_ts, c_bal = _live_balance_cache[user_id]
                        if (now_ts - c_ts) < 30.0:
                            live_balance = c_bal
                if live_balance is None:
                    from backend.auth.security import decrypt_kalshi_key
                    from backend.btc.kalshi_trader import KalshiTrader
                    priv = decrypt_kalshi_key(u.get('kalshi_priv_key_encrypted'))
                    if priv:
                        kt = KalshiTrader(key_id=u.get('kalshi_key_id'), private_key_pem=priv)
                        if kt.is_authenticated():
                            bal = kt.get_balance()
                            if bal.get('success'):
                                live_balance = round(float(bal.get('balance_dollars', 0.0)) + float(bal.get('portfolio_value', 0.0)), 2)
                                with _live_balance_lock:
                                    _live_balance_cache[user_id] = (now_ts, live_balance)
            except Exception as _bal_err:
                logger.warning(f"[AdminUsers] Failed to fetch Kalshi balance for user {user_id}: {_bal_err}")
                live_balance = None

        user_data = {
            "id": user_id,
            "username": u["username"],
            "role": u.get("role", "user"),
            "is_active": bool(u.get("is_active", 1)),
            "trading_mode": user_mode,
            "paper_balance": round(float(u.get("paper_balance", 500.0)), 2),
            "live_balance": live_balance,
            "kalshi_balance": live_balance,
            "balance_available": bool(live_balance is not None) if has_keys else False,
            "has_kalshi_keys": has_keys,
            "ai_enabled": bool(u.get("ai_enabled", 1)),
            # Performance stats
            "total_trades": total_trades,
            "open_trades": open_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "net_pnl": net_pnl,
            "last_trade_time": last_trade_time,
            # Trading & Engine Settings
            "trade_size_dollars": float(u.get("trade_size_dollars", 5.0)),
            "stop_loss_pct": float(u.get("stop_loss_pct", 50.0)),
            "stop_loss_enabled": bool(u.get("stop_loss_enabled", 1)),
            "take_profit_pct": float(u.get("take_profit_pct", 50.0)),
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
            "second_entry_max_ask": float(u.get("second_entry_max_ask", 0.75)),
            "reentry_after_stop_loss": bool(u.get("reentry_after_stop_loss", 0)),
            "max_daily_trades": int(u.get("max_daily_trades", 10)),
            "max_daily_risk": float(u.get("max_daily_risk", 50.0)),
            "model_choice": u.get("model_choice", "RL_DQN"),
            "train_window": int(u.get("train_window", 4000)),
            "regularization_c": float(u.get("regularization_c", 0.5)),
            "class_weight": u.get("class_weight", "balanced"),
            "edge_gate_enabled": bool(u.get("edge_gate_enabled", 1)),
            "min_edge_cents": float(u.get("min_edge_cents", 0.0) or 0.0),
            "use_kelly_criterion": bool(u.get("use_kelly_criterion", 0)),
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
        if is_owner_account(user) and not updates["is_active"]:
            raise HTTPException(status_code=400, detail="The owner account can't be disabled.")
    if updates.get("trading_mode", cur_mode) == "LIVE":
        # For LIVE users the balance field shows the Kalshi balance; it is not a paper balance
        updates.pop("paper_balance", None)

    # Normalize booleans into ints for SQLite if required
    bool_cols = {
        "is_active", "ai_enabled", "one_click_trade", "auto_force_trade",
        "trailing_stop_enabled", "second_entry_enabled", "reentry_after_stop_loss", "ignore_pass_technical", "one_shot_ai",
        "edge_gate_enabled"
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

            new_settings = ex.ai_settings.copy() if hasattr(ex, "ai_settings") and isinstance(ex.ai_settings, dict) else {}
            # Sync snake_case keys
            for k in [
                "trade_size_dollars", "stop_loss_pct", "stop_loss_enabled", "take_profit_pct", "take_profit_enabled", "trading_style",
                "signal_source", "auto_force_trade", "one_click_trade", "trailing_stop_enabled",
                "trailing_stop_activation_pct", "trailing_stop_distance_pct", "second_entry_enabled",
                "second_entry_max_ask", "reentry_after_stop_loss", "ignore_pass_technical", "one_shot_ai",
                "model_choice", "train_window", "regularization_c", "class_weight"
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
            if payload.trailing_stop_enabled is not None:
                new_settings["trailingStopEnabled"] = bool(payload.trailing_stop_enabled)
            if payload.second_entry_enabled is not None:
                new_settings["secondEntryEnabled"] = bool(payload.second_entry_enabled)
            if payload.reentry_after_stop_loss is not None:
                new_settings["reentryAfterStopLoss"] = bool(payload.reentry_after_stop_loss)

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


@router.get("/users/{user_id}/trades")
def get_user_trades(
    user_id: int,
    mode: Optional[str] = None,
    auth: bool = Depends(require_admin_auth)
):
    """Fetch all historical and active trades for a specific user account."""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    from backend.database.trade_store import TradeStore
    trades = TradeStore.get_recent_trades(user_id, limit=200)

    # Optional mode filter
    if mode and mode.upper() in ("PAPER", "LIVE"):
        filtered_trades = [t for t in trades if str(t.get("mode", "PAPER")).upper() == mode.upper()]
    else:
        filtered_trades = trades

    total_count = len(trades)
    open_count = sum(1 for t in trades if t.get("status") == "OPEN")
    closed = [t for t in trades if t.get("status") != "OPEN"]
    wins = sum(1 for t in closed if float(t.get("pnl", 0)) > 0)
    losses = sum(1 for t in closed if float(t.get("pnl", 0)) < 0)
    win_rate = round((wins / len(closed) * 100), 1) if closed else 0.0
    net_pnl = round(sum(float(t.get("pnl", 0)) for t in closed), 2)

    from backend.database.models import enrich_trade_metadata
    user_style = user.get("trading_style", "AUTO")
    user_source = user.get("signal_source", "RL_DQN")
    user_model = user.get("model_choice", "RL_DQN")
    enriched_trades = [
        enrich_trade_metadata(dict(t), default_style=user_style, default_source=user_source, default_model=user_model)
        for t in filtered_trades
    ]

    return {
        "success": True,
        "user_id": user_id,
        "username": user.get("username", f"User #{user_id}"),
        "trading_mode": user.get("trading_mode", "PAPER"),
        "summary": {
            "total_trades": total_count,
            "open_trades": open_count,
            "closed_trades": len(closed),
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "net_pnl": net_pnl,
        },
        "trades": enriched_trades[::-1]  # Return most recent first
    }



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








