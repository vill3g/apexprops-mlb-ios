import datetime
import datetime as dt_mod
import io
import json
import logging
import math
import os
import re
import sqlite3
import threading
import time
from typing import Dict, Optional
import uuid
from zoneinfo import ZoneInfo

import requests.exceptions
from fastapi import APIRouter, Body, Cookie, Depends, File, Header, HTTPException, Query, Response, UploadFile
from starlette.concurrency import run_in_threadpool

from backend.btc.fees import kalshi_order_fee, net_pnl
from backend.btc.kalshi_trader import filled_count as _filled_count

logger = logging.getLogger(__name__)

from pydantic import BaseModel


class CloseTradeRequest(BaseModel):
    action: Optional[str] = None


class TradingModeRequest(BaseModel):
    mode: str

class ManualTradeRequest(BaseModel):
    direction: str
    amount_dollars: float
    asset: Optional[str] = None

class UserConfigRequest(BaseModel):
    trade_size_dollars: Optional[float] = None
    paper_trade_size_dollars: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    stop_loss_enabled: Optional[bool] = None
    one_click_trade: Optional[bool] = None
    auto_force_trade: Optional[bool] = None
    target_asset: Optional[str] = None
    trading_style: Optional[str] = None
    signal_source: Optional[str] = None
    take_profit_pct: Optional[float] = None
    take_profit_enabled: Optional[bool] = None
    max_daily_trades: Optional[int] = None
    max_daily_risk: Optional[float] = None
    trailing_stop_enabled: Optional[bool] = None
    trailing_stop_activation_pct: Optional[float] = None
    trailing_stop_distance_pct: Optional[float] = None
    second_entry_enabled: Optional[bool] = None
    second_entry_max_ask: Optional[float] = None
    reentry_after_stop_loss: Optional[bool] = None
    model_choice: Optional[str] = None
    train_window: Optional[int] = None
    regularization_c: Optional[float] = None
    class_weight: Optional[str] = None
    xgb_estimators: Optional[int] = None
    xgb_max_depth: Optional[int] = None
    xgb_learning_rate: Optional[float] = None
    ignore_pass_technical: Optional[bool] = None
    one_shot_ai: Optional[bool] = None
    trading_mode: Optional[str] = None
    edge_gate_enabled: Optional[bool] = None
    min_edge_cents: Optional[float] = None
    notify_trade_results: Optional[bool] = None
    notify_market_trends: Optional[bool] = None
    use_kelly_criterion: Optional[bool] = None

class ExchangeTransferRequest(BaseModel):
    source_exchange: int = 0
    destination_exchange: int = 2
    amount_dollars: float

from typing import Optional

from backend.auth.security import (INVITE_CODE, create_jwt_token,
                                   decode_jwt_token, encrypt_kalshi_key,
                                   hash_password, verify_password)
from backend.database.models import (create_user, deduct_user_paper_balance,
                                     get_all_active_users, get_user_by_id,
                                     get_user_by_username,
                                     update_user_kalshi_keys,
                                     is_manual_entry, bot_style_from_reason,
                                     update_user_config, update_user_edge_gate,
                                     update_user_ai_enabled, credit_user_paper_balance,
                                     reset_user_paper_balance_and_pnl,
                                     copy_user_settings)

from backend.core.registry import get_auto_executor
from backend.btc.analysis_cache import get_cached_btc_analysis
from backend.database.trade_store import TradeStore as _TS
from backend.database.models import DATA_DIR, get_db_connection
from backend.core.push_notifications import vapid_public_key
from backend.core.push_notifications import save_subscription
from backend.core.push_notifications import has_subscription, send_web_push
router = APIRouter(prefix="/api/auth", tags=["auth"])

USERNAME_PATTERN = r"^[A-Za-z0-9_.-]{3,32}$"   # letters, numbers, _ . - (no HTML/script)


class RegisterRequest(BaseModel):
    username: str
    password: str
    invite_code: str

class LoginRequest(BaseModel):
    username: str
    password: str

class UpdateKeysRequest(BaseModel):
    key_id: str
    private_key: str

def get_current_user(
    authorization: Optional[str] = Header(None),
    saas_token: Optional[str] = Cookie(None)
):
    token = None
    if authorization and authorization.startswith("Bearer "):
        parts = authorization.split(" ")
        if len(parts) > 1:
            candidate = parts[1].strip()
            if candidate and candidate not in ("null", "undefined", "None"):
                token = candidate
    if not token and saas_token:
        token = saas_token

    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    payload = decode_jwt_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = get_user_by_id(payload['user_id'])
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")
    if not user.get("is_active", 1):
        raise HTTPException(status_code=403, detail="This account has been disabled.")
    return user

@router.post("/register")
def register(req: RegisterRequest, response: Response):
    if req.invite_code != INVITE_CODE:
        raise HTTPException(status_code=403, detail="Invalid invite code.")

    if not re.fullmatch(USERNAME_PATTERN, req.username or ""):
        raise HTTPException(status_code=400, detail="Username must be 3-32 characters: letters, numbers, _ . or -")
    
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password too short.")
        
    hashed = hash_password(req.password)
    user_id = create_user(req.username, hashed)
    if not user_id:
        raise HTTPException(status_code=400, detail="Username already exists.")
        
    token = create_jwt_token(user_id, req.username)
    response.set_cookie(
        key="saas_token",
        value=token,
        max_age=60 * 60 * 24 * 90,  # 90 days persistent session
        path="/",
        samesite="none",
        secure=True,
        httponly=True
    )
    return {"success": True, "token": token, "username": req.username}

@router.post("/login")
def login(req: LoginRequest, response: Response):
    user = get_user_by_username(req.username)
    if not user or not verify_password(req.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    if not user.get("is_active", 1):
        raise HTTPException(status_code=403, detail="This account has been disabled.")
        
    token = create_jwt_token(user['id'], user['username'])
    response.set_cookie(
        key="saas_token",
        value=token,
        max_age=60 * 60 * 24 * 90,  # 90 days persistent session
        path="/",
        samesite="none",
        secure=True,
        httponly=True
    )
    return {
        "success": True, 
        "token": token, 
        "username": user['username'],
        "role": user.get('role', 'user'),
        "is_active": bool(user.get('is_active', 1))
    }

@router.post("/logout")
def logout_endpoint(response: Response):
    response.delete_cookie(key="saas_token", path="/")
    return {"success": True, "message": "Logged out successfully."}

@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "success": True, 
        "user_id": current_user['id'],
        "username": current_user['username'],
        "trading_mode": current_user.get("trading_mode", "PAPER"),
        "paper_balance": current_user.get("paper_balance", 500.0),
        "has_kalshi_keys": bool(current_user['kalshi_key_id'] and current_user['kalshi_priv_key_encrypted']),
        "profile_pic": current_user.get("profile_pic")
    }

@router.post("/keys")
def update_keys(req: UpdateKeysRequest, current_user: dict = Depends(get_current_user)):
    pem_str = req.private_key
    if '\n' not in pem_str.strip() and ('BEGIN RSA PRIVATE KEY' in pem_str or 'BEGIN PRIVATE KEY' in pem_str):
        s = pem_str.replace('-----BEGIN RSA PRIVATE KEY-----', 'BEGIN_RSA')
        s = s.replace('-----END RSA PRIVATE KEY-----', 'END_RSA')
        s = s.replace('-----BEGIN PRIVATE KEY-----', 'BEGIN_PK')
        s = s.replace('-----END PRIVATE KEY-----', 'END_PK')
        s = s.replace(' ', '')
        if 'BEGIN_RSA' in s:
            start_marker, end_marker = 'BEGIN_RSA', 'END_RSA'
            real_start, real_end = '-----BEGIN RSA PRIVATE KEY-----', '-----END RSA PRIVATE KEY-----'
        else:
            start_marker, end_marker = 'BEGIN_PK', 'END_PK'
            real_start, real_end = '-----BEGIN PRIVATE KEY-----', '-----END PRIVATE KEY-----'
            
        start_idx = s.find(start_marker) + len(start_marker)
        end_idx = s.find(end_marker)
        b64_data = s[start_idx:end_idx]
        lines = [real_start]
        for i in range(0, len(b64_data), 64):
            lines.append(b64_data[i:i+64])
        lines.append(real_end)
        lines.append('')
        pem_str = '\n'.join(lines)
        
    encrypted_priv = encrypt_kalshi_key(pem_str)
    update_user_kalshi_keys(current_user['id'], req.key_id, encrypted_priv)
    return {"success": True, "message": "Keys securely updated."}


_live_balance_cache = {} # user_id -> (timestamp, balance_dollars)
_live_balance_lock = threading.Lock()

_YES_WORDS = {"ABOVE", "UP", "YES", "BUY YES", "BID YES", "STRONG BULLISH (UP)", "BULLISH (UP)"}
_NO_WORDS = {"BELOW", "DOWN", "NO", "BUY NO", "BID NO", "STRONG BEARISH (DOWN)", "BEARISH (DOWN)"}


def _daily_limit(user):
    try:
        return daily_limit_reason(user, user.get("trading_mode", "PAPER"))
    except Exception as e:
        logger.warning(f"Error: {e}")
        return None


_force_ml_lock = threading.Lock()
_force_ml_last = {}   # user_id -> time of the last accepted FORCE AI request


def _signal_side(direction):
    d = str(direction or "").upper().strip()
    return "yes" if d in _YES_WORDS else ("no" if d in _NO_WORDS else None)


# ── What's New (popup on first open after an update + header bell) ─────────────────
import os as _os

ANNOUNCEMENTS_PATH = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "announcements.json")
UPDATE_BELL_DAYS = 7          # the bell stays in the header this long after an update
_announcements_cache = {"mtime": None, "updates": []}
_announcements_cache_lock = threading.Lock()

def _load_announcements():
    """Newest first. Re-read whenever the file changes (no restart needed)."""
    try:
        mtime = _os.path.getmtime(ANNOUNCEMENTS_PATH)
        with _announcements_cache_lock:
            if mtime != _announcements_cache["mtime"]:
                with open(ANNOUNCEMENTS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                ups = [u for u in (data.get("updates") or []) if isinstance(u, dict) and u.get("id")]
                _announcements_cache.update(mtime=mtime, updates=ups)
            return list(_announcements_cache["updates"])
    except (OSError, ValueError) as e:
        logger.warning(f"[Updates] Could not read announcements.json: {e}")
        with _announcements_cache_lock:
            return list(_announcements_cache["updates"])


class UpdateSeenRequest(BaseModel):
    id: str


@router.get("/updates")
def get_updates(current_user: dict = Depends(get_current_user)):
    ups = _load_announcements()
    if not ups:
        return {"success": True, "latest_id": None, "unread": [], "show_bell": False, "updates": []}
    seen = current_user.get("last_seen_update")
    ids = [u["id"] for u in ups]
    if seen in ids:
        unread = ups[:ids.index(seen)]
    else:
        unread = ups[:1]      # new account or unknown id: just the latest update
    recent = False
    try:
        import datetime as _dt
        age = (_dt.date.today() - _dt.date.fromisoformat(str(ups[0].get("date")))).days
        recent = 0 <= age <= UPDATE_BELL_DAYS
    except (TypeError, ValueError):
        pass
    dismissed = current_user.get("dismissed_update") == ids[0]
    return {"success": True, "latest_id": ids[0], "unread": unread,
            "show_bell": bool(unread) or (recent and not dismissed), "updates": ups[:5]}


@router.post("/updates/seen")
def mark_update_seen(req: UpdateSeenRequest, current_user: dict = Depends(get_current_user)):
    ids = [u["id"] for u in _load_announcements()]
    if req.id not in ids:
        raise HTTPException(status_code=400, detail="Unknown update id.")
    conn = get_db_connection()
    conn.execute("UPDATE users SET last_seen_update = ? WHERE id = ?", (req.id, current_user["id"]))
    conn.commit()
    return {"success": True}


@router.post("/updates/dismiss")
def dismiss_update_bell(req: UpdateSeenRequest, current_user: dict = Depends(get_current_user)):
    """Hide the header bell for this update before its 7 days are up (also marks it read).
    It comes back automatically when a newer update is published."""
    ids = [u["id"] for u in _load_announcements()]
    if req.id not in ids:
        raise HTTPException(status_code=400, detail="Unknown update id.")
    conn = get_db_connection()
    conn.execute("UPDATE users SET last_seen_update = ?, dismissed_update = ? WHERE id = ?",
                 (req.id, req.id, current_user["id"]))
    conn.commit()
    return {"success": True}


_strategy_stats_cache = {"ts": 0.0, "data": None}
_strategy_stats_cache_lock = threading.Lock()
STRATEGY_STATS_DAYS = 30


@router.get("/strategy_stats")
def get_strategy_stats():
    """Real win rate per strategy: closed bot trades of all users over the last 30 days
    (paper and live). Aggregate numbers only, no user data. Cached for 60 s."""


    now = time.time()
    with _strategy_stats_cache_lock:
        if _strategy_stats_cache["data"] and now - _strategy_stats_cache["ts"] < 60:
            return _strategy_stats_cache["data"]
    since = now - STRATEGY_STATS_DAYS * 86400
    stats = {}
    rows = get_db_connection().execute(
        "SELECT raw_json FROM trades WHERE status != 'OPEN' ORDER BY rowid DESC LIMIT 20000").fetchall()
    for (raw,) in rows:
        try:
            t = _json.loads(raw)
        except (TypeError, ValueError):
            continue
        if is_manual_entry(t) or _trade_epoch(t.get("timestamp")) < since:
            continue
        style = bot_style_from_reason(t.get("reason")) or str(t.get("trading_style") or "").upper()
        if not style or style == "MANUAL":
            continue
        pnl = float(t.get("pnl") or 0)
        s = stats.setdefault(style, {"wins": 0, "losses": 0, "pnl": 0.0})
        if pnl > 0:
            s["wins"] += 1
        elif pnl < 0:
            s["losses"] += 1
        s["pnl"] = round(s["pnl"] + pnl, 2)
    for s in stats.values():
        n = s["wins"] + s["losses"]
        s["trades"] = n
        s["win_rate"] = round(100.0 * s["wins"] / n, 1) if n else None
    data = {"success": True, "days": STRATEGY_STATS_DAYS, "styles": stats}
    with _strategy_stats_cache_lock:
        _strategy_stats_cache.update(ts=now, data=data)
    return data


@router.get("/my_signal")
def get_my_signal(current_user: dict = Depends(get_current_user)):
    """What the auto-trader sees and will do for THIS user right now, using the same
    forecast (their style + signal source) and the same gates as the trade engine."""



    style = str(current_user.get("trading_style") or "AUTO").upper()
    source = str(current_user.get("signal_source") or "RL_DQN").upper()
    out = {"success": True, "style": style, "source": source, "action": "WAIT", "status": "", "bias": "PASS",
           "grade": "PASS", "prob_percent": None, "edge_cents": None, "ask": None, "summary": ""}

    if not current_user.get("ai_enabled", 1):
        out.update(status="Auto-trade is of", summary="Turn AUTO on to let the bot trade this signal.")
    if source == "RL_SCALPER":
        try:
            from backend.btc.rl_scalper import scalper_live_enabled
            enabled = scalper_live_enabled()
        except Exception as e:
            logger.warning(f"Error: {e}")
            enabled = False
        if not enabled:
            out.update(action="OFF", status="RL Scalper is switched of",
                       summary="The scalper failed its profitability test, so it places no trades. Choose another signal source in Settings.")
            return out

    market = get_kalshi_15m_market() or {}
    ticker = market.get("ticker", "")
    try:
        with open(SIGNAL_SNAPSHOT_PATH, "r", encoding="utf-8") as f:
            snap = (_json.load(f).get("results") or {}).get(_snapshot_key(style, source))
    except (OSError, ValueError):
        snap = None
    if not snap or snap.get("ticker") != ticker or time.time() - float(snap.get("ts", 0)) > 60:
        out.update(status="Waiting for the trading engine",
                   summary="No fresh forecast for your settings yet (the engine refreshes every few seconds while a market is open).")
        return out

    direction = snap.get("direction", "PASS")
    side = _signal_side(direction)
    prob = snap.get("probability_percent")
    out.update(bias=("YES" if side == "yes" else "NO" if side == "no" else "PASS"),
               grade=("PASS" if not side else str(snap.get("conviction_grade") or "").replace(" SETUP", "")),
               effective_style=snap.get("effective_style"),
               catalysts=snap.get("catalysts", [])[:5],
               flow=(snap.get("chart") or {}).get("flow"),
               sec_left=snap.get("sec_left"))
    forced = False
    if not side:
        if current_user.get("auto_force_trade") or current_user.get("one_shot_ai"):
            mp = snap.get("ml_prob")
            try:
                mp = float(mp)
            except (TypeError, ValueError):
                mp = 0.5
            if mp != 0.5:
                side = "yes" if mp > 0.5 else "no"
                prob = max(51.0, (mp if side == "yes" else 1 - mp) * 100.0)
                forced = True
            else:
                side = _signal_side(snap.get("pre_gate_direction"))
                prob = snap.get("pre_gate_prob") or 51.0
                forced = bool(side)
        elif current_user.get("ignore_pass_technical") and "ML MODEL" not in str(snap.get("pre_gate_grade", "")):
            side = _signal_side(snap.get("pre_gate_direction"))
            prob = snap.get("pre_gate_prob") or 60.0
            forced = bool(side)
    out["prob_percent"] = round(float(prob), 1) if (side and prob is not None) else None
    if forced:
        out["bias"] = side.upper()

    if not side:
        out.update(action="PASS", status="No edge. Bot will pass",
                   summary=(snap.get("catalysts") or ["The model has no trade signal for this market."])[0])
        return out

    ask = market.get(f"{side}_ask")
    try:
        ask = float(ask)
    except (TypeError, ValueError):
        ask = None
    if ask:
        out["ask"] = round(ask, 2)
        out["edge_cents"] = entry_edge_cents(prob, ask)
    label = f"buy {side.upper()}" + (f" at {round(ask * 100)}\u00a2" if ask else "")

    # Same gates as the trade engine (saas_broadcaster)
    sec_left = float(snap.get("sec_left") or 900)
    reason = None
    if not current_user.get("ai_enabled", 1):
        reason = "Auto-trade is of"
    elif sec_left < 180:
        reason = "No new entries in the last 3 minutes"
    elif any(t.get("ticker") == ticker for t in TradeStore.get_recent_trades(current_user["id"], limit=20)):
        reason = "Already traded this market"
    elif _daily_limit(current_user):
        reason = _daily_limit(current_user)
    elif ask is None or ask < 0.15 or ask > 0.85:
        reason = "Price outside the 15\u201385\u00a2 entry range"
    else:
        chart = snap.get("chart") or {}
        strike = float(snap.get("strike") or 0)
        cats = " ".join(snap.get("catalysts", []))
        if chart and strike:
            delta = chart["close"] - strike
            if side == "yes" and delta < -25 and chart["close"] < chart["open"] and chart["ema9"] < chart["ema21"] \
                    and not any(k in cats for k in ("Absorption Hammer", "Oversold Spring", "Bullish Liquidity Sweep")):
                reason = "Blocked: price is below target and trending down"
            elif side == "no" and delta > 25 and chart["close"] > chart["open"] and chart["ema9"] > chart["ema21"] \
                    and not any(k in cats for k in ("Rejection Pin", "Overbought Exhaustion", "Bearish Liquidity Sweep")):
                reason = "Blocked: price is above target and trending up"
    if reason is None and current_user.get("edge_gate_enabled", 1) and out["edge_cents"] is not None:
        min_edge = float(current_user.get("min_edge_cents", 0.0) or 0.0)
        if out["edge_cents"] <= min_edge:
            reason = (f"edge {out['edge_cents']:+.1f}\u00a2 is not above your {min_edge:.1f}\u00a2 minimum (Edge Guard)")
    if reason:
        out.update(action="HOLD", status=f"Signal {side.upper()}, but {reason[0].lower() + reason[1:]}")
    else:
        warn = " (negative edge after fees)" if (out["edge_cents"] is not None and out["edge_cents"] <= 0) else ""
        out.update(action="BUY_" + side.upper(),
                   status=("Forced by your settings: " if forced else "") + f"Bot will {label}{warn}")
    out["summary"] = (snap.get("catalysts") or [""])[0]
    return out


def _market_result(t):
    try:
        from backend.btc.market_results import get_result
        return get_result(t.get("ticker"), t)
    except Exception as e:
        logger.warning(f"Error: {e}")
        return None


def _market_finished(ticker):
    try:
        from backend.btc.market_results import market_finished
        return market_finished(ticker)
    except Exception as e:
        logger.warning(f"Error: {e}")
        return None


@router.get("/dashboard_stats")
def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    
    user_id = current_user['id']
    trades = TradeStore.get_recent_trades(user_id, limit=100)
    
    trading_mode = current_user.get('trading_mode', 'PAPER')
    
    # Show ALL trades in recent executions (open trades, history regardless of mode switch)
    # Stats (wins/losses/PnL) are still filtered to current active mode only
    trades_filtered = trades
            
    # All-time stats for the active mode (not just the most recent 100 trades)
    _mode_stats = TradeStore.get_closed_stats(user_id).get(str(trading_mode).upper(), {})
    wins = int(_mode_stats.get("wins", 0))
    losses = int(_mode_stats.get("losses", 0))
    total_pnl = float(_mode_stats.get("pnl", 0.0))

    
    market_by_series = {}
    live_open_pnl = 0.0
    open_paper_value = 0.0
    open_live_value = 0.0

    for t in trades_filtered:
        tk = str(t.get("ticker") or "").upper()
        # Ensure asset is always tagged
        if not t.get("asset") or t.get("asset") == "None":
            if "BTC" in tk:
                t["asset"] = "BTC"
            elif "ETH" in tk:
                t["asset"] = "ETH"
            elif "GOLD" in tk:
                t["asset"] = "GOLD"
            elif "EURUSD" in tk:
                t["asset"] = "EURUSD"
            elif "GBPUSD" in tk:
                t["asset"] = "GBPUSD"
            elif "USDJPY" in tk:
                t["asset"] = "USDJPY"
            else:
                t["asset"] = "BTC"

        if t.get("status") == "OPEN":
            series = tk.split("-")[0] if "-" in tk else f"KX{t['asset']}15M"
            if series not in market_by_series:
                market_by_series[series] = get_kalshi_15m_market(series_ticker=series)
            m = market_by_series.get(series)

            side = str(t.get("side") or "YES").upper()
            entry = float(t.get("entry_price") or 0.5)
            count = int(t.get("count") or 1)

            exit_price = entry
            if m and m.get("status") in ["active", "synthetic"]:
                if m.get("ticker") == tk:
                    if m.get("status") == "synthetic" and "strike" in t:
                        spot = float(m.get("target_price", 0.0))
                        strike = float(t.get("strike", 0.0))
                        if spot > 0 and strike > 0:
                            pct_move = (spot - strike) / strike
                            sign = 1 if side == "YES" else -1
                            edge = (pct_move * sign) * 500.0
                            exit_price = max(0.01, min(0.99, entry + edge))
                        else:
                            exit_price = float(m.get("yes_bid", entry) if side == "YES" else m.get("no_bid", entry))
                    else:
                        exit_price = float(m.get("yes_bid", entry) if side == "YES" else m.get("no_bid", entry))
                        if exit_price <= 0:
                            prob = float(m.get("yes_prob" if side == "YES" else "no_prob", 50.0)) / 100.0
                            exit_price = prob if prob > 0 else entry
                else:
                    exit_price = entry
            else:
                exit_price = entry

            live_pnl = round((exit_price - entry) * count, 2)
            t["live_pnl"] = live_pnl
            t["exit_bid"] = exit_price
            live_open_pnl += live_pnl

            if t.get("mode", "PAPER") == "PAPER":
                open_paper_value += (count * exit_price)
            else:
                open_live_value += (count * exit_price)
        else:
            if "live_pnl" not in t:
                t["live_pnl"] = float(t.get("pnl_dollars") or t.get("pnl") or 0.0)

    total_pnl += live_open_pnl
    
    balance_dollars = None
    portfolio_value = 0.0
    if trading_mode == 'PAPER':
        cash_balance = round(float(current_user.get("paper_balance", 500.0)), 2)
        portfolio_value = round(cash_balance + open_paper_value, 2)
        balance_dollars = cash_balance
    elif trading_mode == 'LIVE' and current_user.get('kalshi_key_id') and current_user.get('kalshi_priv_key_encrypted'):
        now_ts = time.time()
        cached_bal = None
        with _live_balance_lock:
            if user_id in _live_balance_cache:
                c_ts, c_bal = _live_balance_cache[user_id]
                if (now_ts - c_ts) < 3.0 and c_bal is not None:  # 3s TTL for real-time live responsiveness
                    cached_bal = c_bal
        if cached_bal is not None:
            balance_dollars = cached_bal
        else:
            try:
                priv = decrypt_kalshi_key(current_user['kalshi_priv_key_encrypted'])
                if priv:
                    kt = KalshiTrader(key_id=current_user['kalshi_key_id'], private_key_pem=priv)
                    if kt.is_authenticated():
                        bal = kt.get_balance()
                        if bal.get('success'):
                            # Cash balance is available funds for trade size deduction
                            cash_balance = round(float(bal.get('balance_dollars', 0.0)), 2)
                            portfolio_value = round(cash_balance + float(bal.get('portfolio_value', 0.0)), 2)
                            balance_dollars = cash_balance
                            with _live_balance_lock:
                                _live_balance_cache[user_id] = (now_ts, balance_dollars)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as _e:
                logger.warning(f"[Balance] Live balance fetch failed for user {user_id}: {_e}")

    total_pnl_pct = 0.0
    if balance_dollars is not None and balance_dollars > 0:
        if trading_mode == 'PAPER':
            base_bal = float(current_user.get("paper_balance", 500.0))
            if base_bal > 0:
                total_pnl_pct = round((total_pnl / base_bal) * 100.0, 2)
        else:
            cost_basis = balance_dollars - total_pnl
            if cost_basis > 0:
                total_pnl_pct = round((total_pnl / cost_basis) * 100.0, 2)
            elif balance_dollars > 0:
                total_pnl_pct = round((total_pnl / balance_dollars) * 100.0, 2)
                
    global_ticker_strikes = {}
    try:
        hist_file = os.path.join(DATA_DIR, "trades_history.json")
        if os.path.exists(hist_file):
            with open(hist_file, "r") as _hf:
                _gt = json.load(_hf)
                for _g in _gt:
                    _gtick = _g.get("ticker")
                    _gstr = _g.get("strike")
                    if _gtick and _gstr:
                        try:
                            _gnum = float(_gstr)
                            if not math.isnan(_gnum) and not math.isinf(_gnum) and _gnum > 0:
                                global_ticker_strikes[_gtick] = round(_gnum, 2)
                        except (ValueError, TypeError):
                            pass
    except Exception as _ge:
        logger.debug(f"Failed to load global strikes cache: {_ge}")

    formatted_trades = []
    for t in trades_filtered[:50]:
        # Parse time
        ts = t.get("timestamp")
        iso_str = ""
        time_str = ""
        if isinstance(ts, (int, float)):
            dt_obj = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            iso_str = dt_obj.isoformat()
            time_str = dt_obj.astimezone(ZoneInfo("America/New_York")).strftime("%I:%M:%S %p")
        elif isinstance(ts, str):
            # e.g. "2026-09-23 01:46:09 AM ET"
            try:
                dt_str = ts.replace(" ET", "").strip()
                if "T" in dt_str:
                    # It's an ISO string, e.g. 2026-09-25T11:45:16
                    dt_obj = datetime.datetime.fromisoformat(dt_str)
                    if dt_obj.tzinfo is None:
                        dt_obj = dt_obj.replace(tzinfo=ZoneInfo("America/New_York"))
                else:
                    dt_obj = datetime.datetime.strptime(dt_str, "%Y-%m-%d %I:%M:%S %p")
                    dt_obj = dt_obj.replace(tzinfo=ZoneInfo("America/New_York"))
                iso_str = dt_obj.isoformat()
                time_str = dt_obj.strftime("%I:%M:%S %p")
            except Exception as e:
                logging.getLogger("routes").warning(f"Failed to parse time string {ts}: {e}")
                time_str = ts
                iso_str = ts
        
        # Parse strike safely
        ticker = t.get("ticker", "")
        strike = t.get("strike") or t.get("strike_price") or t.get("target_price") or t.get("target")

        # Check market_snapshot if strike not directly present
        if not strike and t.get("market_snapshot"):
            ms = t.get("market_snapshot")
            if isinstance(ms, str):
                try:
                    ms = json.loads(ms)
                except Exception:
                    ms = {}
            if isinstance(ms, dict):
                strike = ms.get("target") or ms.get("strike") or ms.get("strike_price")

        # Check global ticker strikes cache
        if not strike and ticker and ticker in global_ticker_strikes:
            strike = global_ticker_strikes[ticker]

        # Fallback to numeric value from ticker only if it looks like a real numeric strike (e.g. KXBTC-87500)
        if not strike and "-" in ticker:
            last_part = ticker.split("-")[-1]
            clean_part = last_part.lstrip("T").lstrip("B")
            try:
                val = float(clean_part)
                # For crypto (BTC), interval minutes like 00, 15, 30, 45 are not strikes
                if val > 500:
                    strike = val
            except (ValueError, TypeError):
                pass

        # Validate that strike is a valid finite positive float, otherwise None
        if strike is not None:
            try:
                strike_num = float(strike)
                if math.isnan(strike_num) or math.isinf(strike_num) or strike_num <= 0:
                    strike = None
                else:
                    strike = round(strike_num, 2)
            except (ValueError, TypeError):
                strike = None
                
        # Parse PNL
        pnl = t.get("live_pnl", 0.0) if t.get("status") == "OPEN" else float(t.get("pnl", 0.0))
        
        # Resolve trading style & exit reason
        style = t.get("trading_style") or ""
        reason = str(t.get("reason", "") or "")
        exit_reason = str(t.get("exit_reason", "") or "")

        # If legacy record placed exit reason into 'reason', separate them
        if not exit_reason and any(k in reason for k in ["MANUAL_CLOSE", "SETTLEMENT", "STOP_LOSS", "TAKE_PROFIT", "TRAILING_STOP"]):
            exit_reason = reason
            reason = "AI_COPY"


        is_manual = is_manual_entry(t)
        if not is_manual and str(style).upper() == "MANUAL":
            style = bot_style_from_reason(reason) or ""   # older bot trades saved as MANUAL
        if not style or style == "None":
            if is_manual:
                style = "MANUAL"
            elif "MOMENTUM" in reason:
                style = "MOMENTUM_SURFER"
            elif "SNIPER" in reason:
                style = "SNIPER"
            elif "AMBUSH" in reason:
                style = "AMBUSH"
            elif "CHOP" in reason:
                style = "CHOP"
            elif "THIRD_ENTRY" in reason or t.get("is_third_entry") or t.get("reentry_index") == 3:
                style = "THIRD_ENTRY"
            elif "SECOND_ENTRY" in reason or t.get("is_second_entry") or t.get("reentry_index") == 2:
                style = "SECOND_ENTRY"
            elif "AUTO_FORCE" in reason or "FORCE" in reason:
                style = "FORCE"
            else:
                style = current_user.get("trading_style", "AUTO")

        # Resolve signal source
        source = t.get("signal_source") or ""
        if not is_manual and str(source).upper() in ("MANUAL", "REVERSAL"):
            source = ""
        if not source or source == "None" or str(source).upper() == "REVERSAL":
            if is_manual:
                source = "MANUAL"
            elif "TECHNICAL" in reason:
                source = "TECHNICAL_ONLY"
            elif "SWARM" in reason or "ENSEMBLE" in reason:
                source = "SWARM"
            elif "RL_DQN" in reason or "DQN" in reason:
                source = "RL_DQN"
            elif "AI_SIGNAL" in reason or "AI_COPY" in reason:
                source = current_user.get("signal_source", "BLEND")
            else:
                source = current_user.get("signal_source", "BLEND")
        
        # Resolve probability percent / edge
        prob_pct = t.get("probability_percent")
        if prob_pct is None:
            if t.get("confidence") is not None:
                prob_pct = float(t["confidence"])
            elif t.get("predicted_probability") is not None:
                prob_pct = round(float(t["predicted_probability"]) * 100.0, 1)
            elif t.get("ml_prob") is not None:
                mp = float(t["ml_prob"])
                prob_pct = round(max(mp, 1.0 - mp) * 100.0, 1)
            elif t.get("market_snapshot"):
                ms = t.get("market_snapshot")
                if isinstance(ms, str):
                    try:
                        ms = __import__('json').loads(ms)
                    except Exception as e:
                        logger.warning(f"Error: {e}")
                        ms = {}
                if not isinstance(ms, dict):
                    ms = {}
                if ms.get("probability_percent") is not None:
                    prob_pct = float(ms["probability_percent"])
                elif ms.get("confidence") is not None:
                    prob_pct = float(ms["confidence"])
        else:
            try:
                prob_pct = float(prob_pct)
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse probability_percent {prob_pct}: {e}")
                prob_pct = None

        exit_p = t.get("exit_price")
        if exit_p is None and t.get("status") != "OPEN":
            c = int(t.get("count", 1)) or 1
            e = float(t.get("entry_price", 0.5))
            p = float(t.get("pnl", 0.0))
            exit_p = round(max(0.0, min(1.0, (c * e + p) / c)), 2)
        elif exit_p is not None:
            try:
                exit_p = round(float(exit_p), 2)
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse exit_price {exit_p}: {e}")
                exit_p = None

        formatted_trades.append({
            "id": t.get("id"),
            "time": time_str,
            "timestamp": iso_str,
            "side": t.get("side", "").lower(),
            "strike": strike,
            "pnl_dollars": pnl,
            "status": t.get("status", "CLOSED"),
            "mode": t.get("mode", "PAPER"),
            "count": t.get("count", 0),
            "entry_price": t.get("entry_price", 0.0),
            "exit_price": exit_p,
            "reason": reason or "AUTO",
            "exit_reason": exit_reason if not (exit_reason and "REVERSAL" in str(exit_reason).upper() and (t.get("status") == "OPEN" or not t.get("exit_reason"))) else None,
            "trading_style": style if style != "REVERSAL" else current_user.get("trading_style", "AUTO"),
            "signal_source": source,
            "model_choice": t.get("model_choice", current_user.get("model_choice", "RL_DQN")),
            "probability_percent": prob_pct,
            "confidence": prob_pct,
            "is_profit_reentry": bool(t.get("is_profit_reentry") or t.get("is_second_entry") or t.get("is_third_entry") or "SECOND_ENTRY" in reason or "THIRD_ENTRY" in reason),
            "is_third_entry": bool(t.get("is_third_entry") or t.get("reentry_index") == 3 or "THIRD_ENTRY" in reason),
            "is_reversal": bool(t.get("is_reversal") or t.get("is_reverse") or "REVERSAL" in reason),
            "is_manual": bool(is_manual),
            "ticker": ticker,
            # Kalshi's result for the 15-minute market, even if this trade was sold early
            "official_result": _market_result(t),
            "market_finished": _market_finished(t.get("ticker")),
            "catalysts": t.get("catalysts", []),
            "ml_reasoning": t.get("ml_reasoning", ""),
            "market_snapshot": t.get("market_snapshot"),
            "settled_at": t.get("settled_at"),
            "market_regime": t.get("market_regime") or t.get("regime") or "",
            "direction": t.get("direction") or t.get("prediction_direction") or t.get("side", ""),
            "asset": t.get("asset") or ("BTC" if "BTC" in str(ticker) else "ETH" if "ETH" in str(ticker) else "GOLD" if "GOLD" in str(ticker) else "BTC"),
            "live_pnl": t.get("live_pnl", pnl)
        })

    return {
        "success": True,
        "username": current_user.get("username", "Trader"),
        "profile_pic": current_user.get("profile_pic"),
        "role": current_user.get("role", "user"),
        "user_id": current_user.get("id"),
        "api_configured": bool(current_user.get('kalshi_key_id') and current_user.get('kalshi_priv_key_encrypted')),
        "balance_dollars": balance_dollars,
        "cash_balance": balance_dollars,
        "portfolio_value": portfolio_value,
        "open_live_value": open_live_value,
        "open_paper_value": open_paper_value,
        "trading_mode": trading_mode,
        "ai_enabled": bool(current_user.get("ai_enabled", 1)),
        "trade_size_dollars": float(current_user.get("trade_size_dollars", 5.0)),
        "paper_trade_size_dollars": float(current_user.get("paper_trade_size_dollars", 50.0)),
        "target_asset": current_user.get("target_asset", "BTC"),
        "trading_style": current_user.get("trading_style", "AUTO"),
        "signal_source": current_user.get("signal_source", "RL_DQN"),
        "stop_loss_pct": float(current_user.get("stop_loss_pct", 50.0)),
        "stop_loss_enabled": bool(current_user.get("stop_loss_enabled", 1)),
        "take_profit_pct": float(current_user.get("take_profit_pct", 50.0)),
        "take_profit_enabled": bool(current_user.get("take_profit_enabled", 1)),
        "max_daily_trades": int(current_user.get("max_daily_trades", 10)),
        "max_daily_risk": float(current_user.get("max_daily_risk", 50.0)),
        "trailing_stop_enabled": bool(current_user.get("trailing_stop_enabled", 0)),
        "trailing_stop_activation_pct": float(current_user.get("trailing_stop_activation_pct", 35.0)),
        "trailing_stop_distance_pct": float(current_user.get("trailing_stop_distance_pct", 6.0)),
        "second_entry_enabled": bool(current_user.get("second_entry_enabled", 0)),
        "second_entry_max_ask": float(current_user.get("second_entry_max_ask", 0.75)),
        "reentry_after_stop_loss": bool(current_user.get("reentry_after_stop_loss", 0)),
        "one_click_trade": bool(current_user.get("one_click_trade", 0)),
        "auto_force_trade": bool(current_user.get("auto_force_trade", 0)),
        "model_choice": current_user.get("model_choice", "RL_DQN"),
        "train_window": int(current_user.get("train_window", 4000)),
        "regularization_c": float(current_user.get("regularization_c", 0.5)),
        "class_weight": current_user.get("class_weight", "balanced"),
        "xgb_estimators": int(current_user.get("xgb_estimators", 300)),
        "xgb_max_depth": int(current_user.get("xgb_max_depth", 5)),
        "xgb_learning_rate": float(current_user.get("xgb_learning_rate", 0.1)),
        "ignore_pass_technical": bool(current_user.get("ignore_pass_technical", 0)),
        "one_shot_ai": bool(current_user.get("one_shot_ai", 0)),
        "edge_gate_enabled": bool(current_user.get("edge_gate_enabled", 1)),
        "notify_trade_results": bool(current_user.get("notify_trade_results", 1)),
        "notify_market_trends": bool(current_user.get("notify_market_trends", 1)),
        "min_edge_cents": float(current_user.get("min_edge_cents", 0.0) or 0.0),
        "use_kelly_criterion": bool(current_user.get("use_kelly_criterion", 0)),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": total_pnl_pct,
        "live_open_pnl": round(live_open_pnl, 2),
        "win_rate": round((wins / (wins + losses)) * 100, 1) if (wins + losses) > 0 else 0.0,
        "wins": wins,
        "losses": losses,
        "recent_trades": formatted_trades
    }


@router.get("/trade/{trade_id}")
def get_trade_details(trade_id: str, current_user: dict = Depends(get_current_user)):
    trade = TradeStore.get_trade_by_id(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    # Verify user owns this trade unless admin
    if str(trade.get("user_id")) != str(current_user.get("id")) and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to view this trade")
    return {"success": True, "trade": trade}


@router.post("/trade/config")
def update_trade_config(req: TradingModeRequest, current_user: dict = Depends(get_current_user)):
    mode = req.mode.upper()
    if mode not in ["LIVE", "PAPER"]:
        raise HTTPException(status_code=400, detail="Invalid mode.")
        
    from backend.database.models import is_owner_account
    is_owner = is_owner_account(current_user) or current_user.get("role") == "admin"
    
    if mode == "LIVE":
        has_keys = bool(current_user.get('kalshi_key_id') and current_user.get('kalshi_priv_key_encrypted'))
        if not has_keys and is_owner:
            from backend.btc.kalshi_trader import _kt
            if _kt.is_authenticated():
                has_keys = True
                
        if not has_keys:
            raise HTTPException(
                status_code=403,
                detail="Cannot switch to LIVE trading: No Kalshi API keys linked. Please link your Kalshi API keys in Settings first."
            )
            
    update_user_trading_mode(current_user["id"], mode)
    
    # Synchronize executor in memory
    from backend.core.registry import get_auto_executor
    from backend.routes.engine import invalidate_saas_users_cache
    invalidate_saas_users_cache(current_user["id"])
    
    if is_owner:
        get_auto_executor("BTC").set_mode(mode)
    else:
        get_auto_executor("BTC", guest_id=str(current_user["id"])).set_mode(mode)
        
    return {"success": True, "trading_mode": mode}

@router.post("/trade/manual")
def manual_trade(req: ManualTradeRequest, current_user: dict = Depends(get_current_user)):

    
    amount = req.amount_dollars
    side = req.direction.upper()
    asset = req.asset or current_user.get("target_asset") or "BTC"
    mode = current_user.get('trading_mode', 'PAPER')
    user_id = current_user["id"]
    
    if side not in ["YES", "NO"]:
        raise HTTPException(status_code=400, detail="Direction must be YES or NO")
        
    market = get_kalshi_15m_market(series_ticker=f"KX{asset}15M", allow_synthetic=True)
    if not market or market.get("status") != "active":
        raise HTTPException(status_code=400, detail="No active market right now.")

    close_time_str = market.get("close_time", "")
    if close_time_str:
        try:
            import datetime as dt_mod
            ct = dt_mod.datetime.fromisoformat(close_time_str.replace("Z", "+00:00"))
            sec_left = (ct - dt_mod.datetime.now(dt_mod.timezone.utc)).total_seconds()
            if sec_left < 60:
                raise HTTPException(status_code=400, detail=f"Contract expires in {int(sec_left)}s (< 1m remaining). Manual entries blocked near expiration.")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Error: {e}")
            pass
        
    raw_price = market.get("yes_ask" if side == "YES" else "no_ask")
    price = float(raw_price) if raw_price is not None else 0.0
    if price < 0.02 or price > 0.98:
        raise HTTPException(status_code=400, detail=f"No valid executable ask price available (${price:.2f}).")
    count = int(amount / price)
    while count > 0 and (count * price + kalshi_order_fee(price, count)) > amount:
        count -= 1
    if count < 1:
        raise HTTPException(status_code=400, detail=f"Amount (${amount:.2f}) too low to buy 1 contract at ${price:.2f}.")
        
    # Build trade record
    
    trade_id = str(uuid.uuid4())
    now_est = datetime.datetime.now(ZoneInfo("America/New_York")).isoformat()
    
    trade_rec = {
        "id": trade_id,
        "mode": mode,
        "direction": side,
        "side": side,
        "entry_price": price,
        "count": count,
        "timestamp": now_est,
        "status": "OPEN",
        "pnl": 0.0,
        "reason": "MANUAL",
        "ticker": market.get("ticker"),
        "trading_style": "MANUAL",
        "signal_source": "MANUAL",
        "is_manual": True
    ,
        "strike": market.get("target_price") or market.get("strike_price") or market.get("floor_strike"),
        "market_snapshot": json.dumps(market)
    }
    
    if mode == "LIVE":
        if market.get("is_synthetic") or str(market.get("ticker", "")).endswith("_SYNTH"):
            raise HTTPException(status_code=400, detail="Cannot trade synthetic markets in LIVE mode. Switch to PAPER mode to trade ETH/GOLD.")
            
        priv = decrypt_kalshi_key(current_user['kalshi_priv_key_encrypted'])
        if not priv: raise HTTPException(status_code=400, detail="Invalid kalshi keys.")
        kt = KalshiTrader(key_id=current_user['kalshi_key_id'], private_key_pem=priv)
        if not kt.is_authenticated(): raise HTTPException(status_code=400, detail="Failed to auth with Kalshi.")
        
        bal_res = kt.get_balance()
        if bal_res.get('success'):
            avail_bal = float(bal_res.get('balance_dollars', 0.0))
            order_cost = count * price
            if avail_bal < order_cost:
                raise HTTPException(status_code=400, detail=f"Insufficient Kalshi live balance (${avail_bal:.2f}) for order cost (${order_cost:.2f}).")

        # Place live order
        res = kt.place_order(
            ticker=market.get("ticker"),
            side="yes" if side=="YES" else "no",
            count=count,
            limit_price_dollars=price,
            dry_run=False
        )
        if not res.get("success"):
            raise HTTPException(status_code=400, detail=f"Kalshi Error: {res.get('error')}")
        trade_rec["entry_price"] = float(res.get("filled_price", price))
        trade_rec["id"] = str(res.get("client_order_id", trade_id))
        # H1: an IOC order can partially fill - record what Kalshi actually filled.
        trade_rec["count"] = _filled_count(res, count)
        trade_rec["requested_count"] = count
            
    else:
        # Paper trade
        cost = count * price + kalshi_order_fee(price, count)
        if not deduct_user_paper_balance(user_id, cost):
            curr_bal = current_user.get("paper_balance", 500.0)
            raise HTTPException(status_code=400, detail=f"Insufficient paper balance. Cost: ${cost:.2f}, Bal: ${curr_bal:.2f}")
        
    # Save to JSON under user lock
    TradeStore.insert_trade(user_id, trade_rec)
        
    with _live_balance_lock:
        _live_balance_cache.pop(user_id, None)

    return {"success": True, "trade": trade_rec}



class AIToggleRequest(BaseModel):
    enabled: bool

@router.post("/ai_toggle")
def toggle_ai_signals(req: AIToggleRequest, current_user: dict = Depends(get_current_user)):
    update_user_ai_enabled(current_user["id"], req.enabled)
    return {"success": True, "ai_enabled": req.enabled}


@router.post("/trade/close_all")
def close_all_trades(current_user: dict = Depends(get_current_user)):
    
    user_id = current_user['id']
    mode = current_user.get('trading_mode', 'PAPER')
    market = get_kalshi_15m_market()
    closed_count = 0
    trades = TradeStore.get_open_trades(user_id)
            
    # 1. LIVE Close
    if mode == 'LIVE':
        priv = decrypt_kalshi_key(current_user.get('kalshi_priv_key_encrypted', ''))
        if not priv: raise HTTPException(status_code=400, detail="Invalid kalshi keys.")
        kt = KalshiTrader(key_id=current_user.get('kalshi_key_id'), private_key_pem=priv)
        if not kt.is_authenticated(): raise HTTPException(status_code=400, detail="Failed to auth with Kalshi.")
        
        # Map of (ticker, side) -> exit_price
        close_exit_prices = {}
        pos_resp = kt.get_positions()
        if pos_resp and pos_resp.get('success'):
            positions = pos_resp.get('positions', [])
            for p in positions:
                ticker = p.get('ticker')
                yes_pos = int(kt._extract_side_position(p, 'YES'))
                no_pos = int(kt._extract_side_position(p, 'NO'))
                if yes_pos > 0:
                    c_res = kt.close_position(ticker=ticker, purchased_side="yes", count=yes_pos, dry_run=False)
                    if c_res.get("success"):
                        close_exit_prices[(ticker, "YES")] = float(c_res.get("exit_price", 0.5))
                    else:
                        err_msg = str(c_res.get("error", "")).lower()
                        if "finalized" in err_msg or "not open" in err_msg or "closed" in err_msg:
                            m_res = kt.get_market_result(ticker)
                            if m_res.get("success") and m_res.get("result"):
                                close_exit_prices[(ticker, "YES")] = 1.0 if m_res.get("result").upper() == "YES" else 0.0
                    closed_count += 1
                if no_pos > 0:
                    c_res = kt.close_position(ticker=ticker, purchased_side="no", count=no_pos, dry_run=False)
                    if c_res.get("success"):
                        close_exit_prices[(ticker, "NO")] = float(c_res.get("exit_price", 0.5))
                    else:
                        err_msg = str(c_res.get("error", "")).lower()
                        if "finalized" in err_msg or "not open" in err_msg or "closed" in err_msg:
                            m_res = kt.get_market_result(ticker)
                            if m_res.get("success") and m_res.get("result"):
                                close_exit_prices[(ticker, "NO")] = 1.0 if m_res.get("result").upper() == "NO" else 0.0
                    closed_count += 1
                    
        # Update JSON statuses
        for t in trades:
            if t.get("status") == "OPEN" and t.get("mode") == "LIVE":
                entry = float(t.get("entry_price", 0.5))
                count = int(t.get("count", 0))
                side = str(t.get("side", "YES")).upper()
                ticker = t.get("ticker", "")
                
                exit_price = close_exit_prices.get((ticker, side))
                if exit_price is None:
                    c_res = kt.close_position(ticker=ticker, purchased_side=side.lower(), count=count, dry_run=False)
                    if c_res.get("success"):
                        exit_price = float(c_res.get("exit_price", 0.5))
                    else:
                        m_res = kt.get_market_result(ticker)
                        if m_res.get("success") and m_res.get("result"):
                            win = (m_res.get("result").upper() == side)
                            exit_price = 1.0 if win else 0.0
                        else:
                            continue  # Cannot close on Kalshi, leave open

                t["status"] = "CLOSED"
                t["exit_reason"] = "MANUAL_CLOSE"
                t["exit_price"] = round(exit_price, 4)
                t["pnl"] = net_pnl(entry, exit_price, count)
                t["settled_at"] = time.time()
                closed_count += 1
                
    # 2. PAPER Close
    else:
        total_credit = 0.0
        kt_pub = KalshiTrader()
        for t in trades:
            if t.get("status") == "OPEN" and t.get("mode", "PAPER") == "PAPER":
                entry = float(t.get("entry_price", 0.5))
                count = int(t.get("count", 0))
                side = str(t.get("side", "YES")).upper()
                ticker = t.get("ticker", "")
                
                raw_exit = None
                if market and market.get("status") == "active" and market.get("ticker") == ticker:
                    raw_exit = market.get("yes_bid") if side == "YES" else market.get("no_bid")
                else:
                    quote_data = kt_pub.get_market_quote(ticker)
                    if quote_data.get("success"):
                        raw_exit = quote_data.get("yes_bid") if side == "YES" else quote_data.get("no_bid")
                    else:
                        m_res = kt_pub.get_market_result(ticker)
                        if m_res.get("success") and m_res.get("result"):
                            win = (m_res.get("result").upper() == side)
                            raw_exit = 1.0 if win else 0.0
                
                if raw_exit is None or float(raw_exit) < 0:
                    exit_price = entry
                else:
                    exit_price = float(raw_exit)

                _close = {
                    "exit_reason": "MANUAL_CLOSE",
                    "exit_price": round(exit_price, 4),
                    "pnl": net_pnl(entry, exit_price, count),
                    "settled_at": time.time(),
                }
                if not TradeStore.close_if_open(user_id, t, _close):
                    continue  # already closed elsewhere — don't credit twice
                total_credit += count * exit_price - kalshi_order_fee(exit_price, count)
                t.update(_close)
                t["status"] = "CLOSED"
                closed_count += 1
                
        if total_credit > 0:
            credit_user_paper_balance(user_id, total_credit)
            
    # Update SQLite DB for all closed trades (PAPER ones were already closed atomically above)
    for t in trades:
        if t.get("status") == "CLOSED" and t.get("exit_reason") == "MANUAL_CLOSE":
            TradeStore.close_if_open(user_id, t, {
                "status": "CLOSED",
                "exit_reason": "MANUAL_CLOSE",
                "exit_price": t["exit_price"],
                "pnl": t["pnl"],
                "settled_at": t.get("settled_at")
            })
        
    with _live_balance_lock:
        _live_balance_cache.pop(user_id, None)

    return {"success": True, "closed_count": closed_count}

@router.post("/trade/close/{trade_id}")
def close_individual_trade(
    trade_id: str, 
    action: Optional[str] = Query(None),
    payload: Optional[CloseTradeRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    if payload and hasattr(payload, 'action') and payload.action:
        action = payload.action

    user_id = current_user['id']
    trades = TradeStore.get_open_trades(user_id)
    target_trade = next((t for t in trades if t.get('id') == trade_id and t.get('status') == 'OPEN'), None)
    if not target_trade:
        raise HTTPException(status_code=404, detail="Open trade not found.")
    # Close according to how the trade was opened, not the account's current mode
    mode = str(target_trade.get('mode') or current_user.get('trading_mode', 'PAPER')).upper()

    ticker = target_trade.get('ticker')
    side = str(target_trade.get('side', '')).lower()
    count = int(target_trade.get('count', 0))
    entry = float(target_trade.get("entry_price", 0.5))

    exit_price = entry  # Fallback

    if mode == 'LIVE':
        priv = decrypt_kalshi_key(current_user.get('kalshi_priv_key_encrypted', ''))
        if not priv: raise HTTPException(status_code=400, detail="Invalid kalshi keys.")
        kt = KalshiTrader(key_id=current_user.get('kalshi_key_id'), private_key_pem=priv)
        if not kt.is_authenticated(): raise HTTPException(status_code=400, detail="Failed to auth with Kalshi.")
        
        if count > 0:
            close_res = kt.close_position(ticker=ticker, purchased_side=side, count=count, dry_run=False)
            if close_res.get("success"):
                exit_price = float(close_res.get("exit_price", entry))
            else:
                err_msg = str(close_res.get("error", "")).lower()
                if "finalized" in err_msg or "not open" in err_msg or "closed" in err_msg:
                    m_res = kt.get_market_result(ticker)
                    if m_res.get("success") and m_res.get("result"):
                        win = (m_res.get("result").upper() == side.upper())
                        exit_price = 1.0 if win else 0.0
                    else:
                        raise HTTPException(status_code=400, detail="Market already finalizing/closed. Trade will settle shortly.")
                else:
                    raise HTTPException(status_code=400, detail=close_res.get("error", "Live close failed."))
        
    else:
        market = get_kalshi_15m_market()
        raw_exit = None
        if market and market.get("status") == "active" and market.get("ticker") == ticker:
            raw_exit = market.get("yes_bid") if side.upper() == "YES" else market.get("no_bid")
        else:
            kt_pub = KalshiTrader()
            quote_data = kt_pub.get_market_quote(ticker)
            if quote_data.get("success"):
                raw_exit = quote_data.get("yes_bid") if side.upper() == "YES" else quote_data.get("no_bid")
            else:
                m_res = kt_pub.get_market_result(ticker)
                if m_res.get("success") and m_res.get("result"):
                    win = (m_res.get("result").upper() == side.upper())
                    raw_exit = 1.0 if win else 0.0

        if raw_exit is None or float(raw_exit) < 0:
            raise HTTPException(status_code=400, detail="Cannot close: No bids available on orderbook.")

        exit_price = float(raw_exit)

    req_action_upper = str(action or "").upper()
    is_take_profit = ("PROFIT" in req_action_upper) or (exit_price > entry and req_action_upper != "MANUAL_CLOSE")
    resolved_exit_reason = "TAKE_PROFIT" if is_take_profit else "MANUAL_CLOSE"

    target_trade["status"] = "CLOSED"
    target_trade["exit_reason"] = resolved_exit_reason
    if is_take_profit:
        target_trade["is_manual"] = False  # preserve AI bot trade classification
    target_trade["exit_price"] = round(exit_price, 4)
    target_trade["pnl"] = net_pnl(entry, exit_price, count)
    target_trade["settled_at"] = time.time()
        
    claimed = TradeStore.close_if_open(user_id, target_trade, {
        "exit_reason": resolved_exit_reason,
        "exit_price": target_trade["exit_price"],
        "pnl": target_trade["pnl"],
        "settled_at": target_trade.get("settled_at")
    })
    if mode != 'LIVE':
        if not claimed:
            raise HTTPException(status_code=409, detail="Trade was already closed.")
        # Credit exactly once — only the caller that actually closed the trade
        credit_user_paper_balance(user_id, count * exit_price - kalshi_order_fee(exit_price, count))

    with _live_balance_lock:
        _live_balance_cache.pop(user_id, None)

    reentry_trade = None
    if is_take_profit:
        # 1. Release order_intents for this user on this ticker so automated orders are not blocked
        try:
            from backend.database import order_intents
            acc_key = order_intents.account_key_for_user(user_id)
            order_intents.release(acc_key, ticker)
            order_intents.release(acc_key, f"{ticker}#second_entry")
            order_intents.release(acc_key, f"{ticker}#third_entry")
        except Exception as _oe:
            logger.warning(f"[Routes] Failed to release order_intents for user {user_id}: {_oe}")

        # 2. Release in-memory interval lockout cache for this user
        try:
            from backend.btc.auto_executor.shared import _user_last_traded_cache, _user_last_traded_lock
            with _user_last_traded_lock:
                for k in [k for k in _user_last_traded_cache if k[0] == user_id]:
                    _user_last_traded_cache.pop(k, None)
        except Exception as _ce:
            logger.warning(f"[Routes] Failed to release _user_last_traded_cache for user {user_id}: {_ce}")

        # 3. Clear single-tenant auto-executor lockout if running
        try:
            from backend.core.registry import get_auto_executor
            ex = get_auto_executor()
            if ex:
                ex.last_traded_interval = None
        except Exception:
            pass

        # 4. Immediately evaluate tactical pullback re-entry (2nd / 3rd entry DCA)
        try:
            from backend.saas_settler import trigger_saas_take_profit_reentry
            reentry_trade = trigger_saas_take_profit_reentry(
                user_id=user_id,
                closed_trade=target_trade,
                exit_price=exit_price,
                is_user_initiated=True,
                live_kt=kt if mode == 'LIVE' and 'kt' in locals() else None
            )
        except Exception as _re:
            logger.error(f"[Routes] Error triggering take profit re-entry for user {user_id}: {_re}", exc_info=True)

    # Sync to user's trades_history.json file on disk if it exists
    try:
        from backend.database.models import DATA_DIR
        hist_path = os.path.join(DATA_DIR, 'users', str(user_id), 'trades_history.json')
        if os.path.exists(hist_path):
            from backend.btc.io_utils import atomic_json_write
            with open(hist_path, 'r', encoding='utf-8') as f:
                disk_trades = json.load(f)
            found = False
            for dt in disk_trades:
                if dt.get('id') == trade_id:
                    dt['status'] = 'CLOSED'
                    dt['exit_reason'] = resolved_exit_reason
                    dt['exit_price'] = target_trade['exit_price']
                    dt['pnl'] = target_trade['pnl']
                    dt['settled_at'] = target_trade['settled_at']
                    if is_take_profit:
                        dt['is_manual'] = False
                    found = True
                    break
            if found:
                atomic_json_write(hist_path, disk_trades, indent=4)
    except Exception as _he:
        logger.warning(f"[Routes] Could not update disk trades_history.json: {_he}")

    return {
        "success": True, 
        "trade_id": trade_id, 
        "exit_price": exit_price, 
        "pnl": target_trade["pnl"],
        "exit_reason": resolved_exit_reason,
        "reentry_triggered": bool(reentry_trade),
        "reentry_trade": reentry_trade
    }


@router.post("/trade/take_profit/{trade_id}")
def take_profit_individual_trade(trade_id: str, current_user: dict = Depends(get_current_user)):
    return close_individual_trade(trade_id=trade_id, action="TAKE_PROFIT", payload=None, current_user=current_user)


@router.post("/user/config")
def set_user_config(req: UserConfigRequest, current_user: dict = Depends(get_current_user)):
    update_user_config(
        current_user["id"], 
        req.trade_size_dollars if req.trade_size_dollars is not None else float(current_user.get("trade_size_dollars", 5.0)),
        req.paper_trade_size_dollars if req.paper_trade_size_dollars is not None else float(current_user.get("paper_trade_size_dollars", 50.0)),
        req.stop_loss_pct if req.stop_loss_pct is not None else float(current_user.get("stop_loss_pct", 50.0)),
        req.stop_loss_enabled if req.stop_loss_enabled is not None else bool(current_user.get("stop_loss_enabled", 1)),
        req.one_click_trade if req.one_click_trade is not None else bool(current_user.get("one_click_trade", 0)),
        req.auto_force_trade if req.auto_force_trade is not None else bool(current_user.get("auto_force_trade", 0)),
        req.target_asset if req.target_asset is not None else current_user.get("target_asset", "BTC"),
        req.trading_style if req.trading_style is not None else current_user.get("trading_style", "AUTO"),
        req.signal_source if req.signal_source is not None else current_user.get("signal_source", "RL_DQN"),
        req.take_profit_pct if req.take_profit_pct is not None else float(current_user.get("take_profit_pct", 50.0)),
        req.take_profit_enabled if req.take_profit_enabled is not None else bool(current_user.get("take_profit_enabled", 1)),
        req.max_daily_trades if req.max_daily_trades is not None else int(current_user.get("max_daily_trades", 10)),
        req.max_daily_risk if req.max_daily_risk is not None else float(current_user.get("max_daily_risk", 50.0)),
        req.trailing_stop_enabled if req.trailing_stop_enabled is not None else bool(current_user.get("trailing_stop_enabled", 0)),
        req.trailing_stop_activation_pct if req.trailing_stop_activation_pct is not None else float(current_user.get("trailing_stop_activation_pct", 35.0)),
        req.trailing_stop_distance_pct if req.trailing_stop_distance_pct is not None else float(current_user.get("trailing_stop_distance_pct", 6.0)),
        req.second_entry_enabled if req.second_entry_enabled is not None else bool(current_user.get("second_entry_enabled", 0)),
        req.second_entry_max_ask if req.second_entry_max_ask is not None else float(current_user.get("second_entry_max_ask", 0.75)),
        req.reentry_after_stop_loss if req.reentry_after_stop_loss is not None else bool(current_user.get("reentry_after_stop_loss", 0)),
        req.model_choice if req.model_choice is not None else current_user.get("model_choice", "RL_DQN"),
        req.train_window if req.train_window is not None else int(current_user.get("train_window", 4000)),
        req.regularization_c if req.regularization_c is not None else float(current_user.get("regularization_c", 0.5)),
        req.class_weight if req.class_weight is not None else current_user.get("class_weight", "balanced"),
        req.xgb_estimators if req.xgb_estimators is not None else int(current_user.get("xgb_estimators", 300)),
        req.xgb_max_depth if req.xgb_max_depth is not None else int(current_user.get("xgb_max_depth", 5)),
        req.xgb_learning_rate if req.xgb_learning_rate is not None else float(current_user.get("xgb_learning_rate", 0.1)),
        req.ignore_pass_technical if req.ignore_pass_technical is not None else bool(current_user.get("ignore_pass_technical", 0)),
        req.one_shot_ai if req.one_shot_ai is not None else bool(current_user.get("one_shot_ai", 0)),
        req.notify_trade_results if req.notify_trade_results is not None else bool(current_user.get("notify_trade_results", 1)),
        req.notify_market_trends if req.notify_market_trends is not None else bool(current_user.get("notify_market_trends", 1)),
        req.use_kelly_criterion if req.use_kelly_criterion is not None else bool(current_user.get("use_kelly_criterion", 0)),
    )

    if req.edge_gate_enabled is not None or req.min_edge_cents is not None:
        update_user_edge_gate(current_user["id"], req.edge_gate_enabled, req.min_edge_cents)
    
    if req.trading_mode:
        m = req.trading_mode.strip().upper()
        if m in ["LIVE", "PAPER"]:
            if m == "LIVE":
                if not current_user.get('kalshi_key_id') or not current_user.get('kalshi_priv_key_encrypted'):
                    raise HTTPException(
                        status_code=400,
                        detail="Cannot switch to LIVE trading: No Kalshi API keys linked. Please link your Kalshi API keys in Settings first."
                    )
            update_user_trading_mode(current_user["id"], m)
    
    u_fresh = get_user_by_id(current_user["id"]) or current_user

    # Immediately apply to current live engine memory
    ex = get_auto_executor("BTC", guest_id=current_user["id"])
    new_settings = ex.ai_settings.copy() if hasattr(ex, 'ai_settings') else {}
    new_settings["trade_size_dollars"] = float(u_fresh.get("trade_size_dollars", 5.0))
    new_settings["paper_trade_size_dollars"] = float(u_fresh.get("paper_trade_size_dollars", 50.0))
    new_settings["stop_loss_pct"] = float(u_fresh.get("stop_loss_pct", 50.0))
    new_settings["stopLossPercent"] = float(u_fresh.get("stop_loss_pct", 50.0))
    new_settings["stop_loss_enabled"] = bool(u_fresh.get("stop_loss_enabled", 1))
    new_settings["stopLossEnabled"] = bool(u_fresh.get("stop_loss_enabled", 1))
    new_settings["one_click_trade"] = bool(u_fresh.get("one_click_trade", 0))
    new_settings["auto_force_trade"] = bool(u_fresh.get("auto_force_trade", 0))
    new_settings["target_asset"] = u_fresh.get("target_asset", "BTC")
    new_settings["trading_style"] = u_fresh.get("trading_style", "AUTO")
    new_settings["signal_source"] = u_fresh.get("signal_source", "RL_DQN")
    new_settings["take_profit_pct"] = float(u_fresh.get("take_profit_pct", 50.0))
    new_settings["takeProfitPercent"] = float(u_fresh.get("take_profit_pct", 50.0))
    new_settings["take_profit_enabled"] = bool(u_fresh.get("take_profit_enabled", 1))
    new_settings["takeProfitEnabled"] = bool(u_fresh.get("take_profit_enabled", 1))
    new_settings["max_daily_trades"] = int(u_fresh.get("max_daily_trades", 10))
    new_settings["max_daily_risk"] = float(u_fresh.get("max_daily_risk", 50.0))
    new_settings["trailing_stop_enabled"] = bool(u_fresh.get("trailing_stop_enabled", 0))
    new_settings["trailingStopEnabled"] = bool(u_fresh.get("trailing_stop_enabled", 0))
    new_settings["trailing_stop_activation_pct"] = float(u_fresh.get("trailing_stop_activation_pct", 35.0))
    new_settings["trailing_stop_distance_pct"] = float(u_fresh.get("trailing_stop_distance_pct", 6.0))
    new_settings["second_entry_enabled"] = bool(u_fresh.get("second_entry_enabled", 0))
    new_settings["secondEntryEnabled"] = bool(u_fresh.get("second_entry_enabled", 0))
    new_settings["second_entry_max_ask"] = float(u_fresh.get("second_entry_max_ask", 0.75))
    new_settings["reentry_after_stop_loss"] = bool(u_fresh.get("reentry_after_stop_loss", 0))
    new_settings["reentryAfterStopLoss"] = bool(u_fresh.get("reentry_after_stop_loss", 0))
    
    new_settings["model_choice"] = u_fresh.get("model_choice", "RL_DQN")
    new_settings["train_window"] = int(u_fresh.get("train_window", 4000))
    new_settings["regularization_c"] = float(u_fresh.get("regularization_c", 0.5))
    new_settings["class_weight"] = u_fresh.get("class_weight", "balanced")
    new_settings["xgb_estimators"] = int(u_fresh.get("xgb_estimators", 300))
    new_settings["xgb_max_depth"] = int(u_fresh.get("xgb_max_depth", 5))
    new_settings["xgb_learning_rate"] = float(u_fresh.get("xgb_learning_rate", 0.1))
    new_settings["ignore_pass_technical"] = bool(u_fresh.get("ignore_pass_technical", 0))
    new_settings["one_shot_ai"] = bool(u_fresh.get("one_shot_ai", 0))
    new_settings["use_kelly_criterion"] = bool(u_fresh.get("use_kelly_criterion", 0))
    new_settings["useKellyCriterion"] = bool(u_fresh.get("use_kelly_criterion", 0))

    ex.set_ai_settings(new_settings)
    
    # Set the execution bounds directly on the executor instance
    ex.set_risk_limits(
        max_daily_risk=float(u_fresh.get("max_daily_risk", 50.0)),
        max_daily_trades=int(u_fresh.get("max_daily_trades", 10))
    )
    
    return {"success": True}

@router.post("/trade/force_ml")
def force_ml_trade(current_user: dict = Depends(get_current_user)):
    # 1. Get ML Analysis
    try:
        _, analysis = get_cached_btc_analysis(asset="BTC", timeframe="15m")
    except (json.JSONDecodeError, FileNotFoundError, OSError, ValueError, KeyError) as e:
        logger.error(f"Failed to fetch ML analysis: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch ML analysis")
        
    forecast = analysis.get("target_benchmark", {}).get("next_contract_forecast", {})
    forecast_dir = str(forecast.get("direction", "")).upper().strip()
    
    if forecast_dir in ["ABOVE", "UP", "YES"]:
        direction = "YES"
    elif forecast_dir in ["BELOW", "DOWN", "NO"]:
        direction = "NO"
    else:
        # Fallback to general bias if forecast is PASS or missing
        bias = str(analysis.get("direction", "")).upper().strip()
        if "UP" in bias or "BULLISH" in bias:
            direction = "YES"
        elif "DOWN" in bias or "BEARISH" in bias:
            direction = "NO"
        else:
            # Check pre-gate direction or probability if both forecast and bias are neutral
            pre_dir = str(forecast.get("pre_gate_direction", "")).upper().strip()
            if pre_dir in ["ABOVE", "UP", "YES"]:
                direction = "YES"
            elif pre_dir in ["BELOW", "DOWN", "NO"]:
                direction = "NO"
            else:
                ml_p = float(forecast.get("predicted_probability") or forecast.get("ml_prob") or 0.5)
                if ml_p > 0.50:
                    direction = "YES"
                elif ml_p < 0.50:
                    direction = "NO"
                else:
                    conf = float(analysis.get("confluence_score", 50.0))
                    direction = "YES" if conf >= 50.0 else "NO"
    # 2. Get Market
    market = get_kalshi_15m_market()
    if not market or market.get("status") != "active":
        raise HTTPException(status_code=400, detail="No active market found.")

    # A double tap used to place the same trade twice (seen 27 Sep: two identical trades
    # in the same second). Accept one FORCE AI request per user per 10 s and per market.
    uid = current_user["id"]
    with _force_ml_lock:
        now_t = time.time()
        if now_t - _force_ml_last.get(uid, 0) < 5:
            raise HTTPException(status_code=429, detail="Force AI was just used. Wait a moment before trying again.")
        if any(t.get("ticker") == market.get("ticker") and t.get("reason") == "FORCE_ML_COPY" and t.get("status") == "OPEN"
               for t in _TS.get_recent_trades(uid, limit=10)):
            raise HTTPException(status_code=400, detail="You already have an open Force AI trade on this market.")
        _force_ml_last[uid] = now_t

    close_time_str = market.get("close_time", "")
    if close_time_str:
        try:
            import datetime as dt_mod
            ct = dt_mod.datetime.fromisoformat(close_time_str.replace("Z", "+00:00"))
            sec_left = (ct - dt_mod.datetime.now(dt_mod.timezone.utc)).total_seconds()
            if sec_left < 45:
                raise HTTPException(status_code=400, detail=f"Contract expires in {int(sec_left)}s (< 45s remaining). New entries blocked for expiration safety.")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Error checking close time: {e}")

    raw_price = market.get("yes_ask" if direction == "YES" else "no_ask")
    price = float(raw_price) if raw_price is not None else 0.0
    if price < 0.01 or price > 0.99:
        raise HTTPException(status_code=400, detail=f"Contract price (${price:.2f}) outside executable bounds ($0.01 - $0.99).")
        
    mode = current_user.get("trading_mode", "PAPER")
    user_id = current_user["id"]
    if mode == "PAPER":
        risk_amount = float(current_user.get("paper_trade_size_dollars", 50.0))
    else:
        risk_amount = float(current_user.get("trade_size_dollars", 5.0))
    count = int(risk_amount / max(0.01, price))
    while count > 0 and (count * price) > risk_amount:
        count -= 1
    if count < 1:
        raise HTTPException(status_code=400, detail=f"Contract price (${price:.2f}) exceeds configured trade size (${risk_amount:.2f}).")
    trade_id = str(uuid.uuid4())
    
    # 3. Execute
    if mode == "LIVE":
        if not current_user.get('kalshi_key_id') or not current_user.get('kalshi_priv_key_encrypted'):
            raise HTTPException(status_code=400, detail="No Kalshi credentials linked.")
        priv = decrypt_kalshi_key(current_user['kalshi_priv_key_encrypted'])
        kt = KalshiTrader(key_id=current_user['kalshi_key_id'], private_key_pem=priv)
        if not kt.is_authenticated():
            raise HTTPException(status_code=400, detail="Kalshi authentication failed.")
            
        bal_res = kt.get_balance()
        if not bal_res.get('success'):
            raise HTTPException(status_code=400, detail="Failed to get live balance.")
            
        avail_bal = float(bal_res.get('balance_dollars', 0.0))
        if avail_bal < price:
            raise HTTPException(status_code=400, detail=f"Insufficient live Kalshi balance (${avail_bal:.2f}) to purchase 1 contract at ${price:.2f}.")
            
        risk_amount = min(risk_amount, avail_bal)
        count = max(1, int(risk_amount / max(0.01, price)))
        while count > 1 and (count * price + kalshi_order_fee(price, count)) > risk_amount:
            count -= 1
            
        res = kt.place_order(
            ticker=market.get("ticker"),
            side="yes" if direction=="YES" else "no",
            count=count,
            limit_price_dollars=price,
            dry_run=False
        )
        if not res.get('success'):
            raise HTTPException(status_code=400, detail=f"Order failed: {res.get('error')}")
        # H1: record what Kalshi actually filled, at the actual price.
        count = _filled_count(res, count)
        price = float(res.get("filled_price", price) or price)
        trade_id = str(res.get("client_order_id", trade_id))
            
    else:
        # PAPER
        cost = count * price + kalshi_order_fee(price, count)
        if not deduct_user_paper_balance(user_id, cost):
            avail_bal = float(current_user.get('paper_balance', 500.0))
            raise HTTPException(status_code=400, detail=f"Insufficient paper balance. Cost: ${cost:.2f}, Bal: ${avail_bal:.2f}")


    now_est = datetime.datetime.now(ZoneInfo("America/New_York")).isoformat()

    trade_record = {
        "id": trade_id,
        "ticker": market.get("ticker"),
        "side": direction,
        "direction": direction,
        "count": count,
        "entry_price": price,
        "status": "OPEN",
        "pnl": 0.0,
        "timestamp": now_est,
        "mode": mode,
        "reason": "FORCE_ML_COPY",
        "trading_style": current_user.get("trading_style", "AUTO"),
        "signal_source": current_user.get("signal_source", "RL_DQN")
    }
    TradeStore.insert_trade(user_id, trade_record)
    with _live_balance_lock:
        _live_balance_cache.pop(user_id, None)
    return {"success": True, "count": count, "side": direction, "price": price}


@router.post("/trade/reverse")
def reverse_trade(current_user: dict = Depends(get_current_user)):
    """1-Click manual reverse of the user's active position."""
    user_id = current_user["id"]
    mode = current_user.get("trading_mode", "PAPER")

    # 1. Fetch user's open trades
    open_trades = TradeStore.get_open_trades(user_id)
    if not open_trades:
        raise HTTPException(status_code=400, detail="No open positions to reverse. Place a trade first!")

    last_trade = open_trades[-1]
    curr_side = str(last_trade.get("side", "")).upper()
    if curr_side not in ["YES", "NO"]:
        curr_dir = str(last_trade.get("direction", "")).upper()
        curr_side = "YES" if curr_dir in ["ABOVE", "BUY", "YES"] else "NO"

    opposite_side = "NO" if curr_side == "YES" else "YES"

    # 2. Close all existing open trades for this user
    try:
        close_all_trades(current_user=current_user)
    except Exception as e:
        logger.warning(f"Error during reverse closing previous trades: {e}")

    # 3. Get active market to open reversed position
    market = get_kalshi_15m_market()
    if not market or market.get("status") != "active":
        raise HTTPException(status_code=400, detail="Position closed, but no active 15m contract found to reverse into.")

    close_time_str = market.get("close_time", "")
    if close_time_str:
        try:
            import datetime as dt_mod
            ct = dt_mod.datetime.fromisoformat(close_time_str.replace("Z", "+00:00"))
            sec_left = (ct - dt_mod.datetime.now(dt_mod.timezone.utc)).total_seconds()
            if sec_left < 45:
                raise HTTPException(status_code=400, detail=f"Position closed, but contract expires in {int(sec_left)}s. Reverse entries blocked near expiration.")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Error checking close time: {e}")

    # 4. Check price for the opposite side
    raw_price = market.get("yes_ask" if opposite_side == "YES" else "no_ask")
    price = float(raw_price) if raw_price is not None else 0.0
    if price < 0.01 or price > 0.99:
        raise HTTPException(status_code=400, detail=f"Position closed, but opposite ask price (${price:.2f}) is outside valid trading bounds.")

    # 5. Position sizing: match previous trade count if valid, or use user configured size
    if mode == "PAPER":
        risk_amount = float(current_user.get("paper_trade_size_dollars", 50.0))
    else:
        risk_amount = float(current_user.get("trade_size_dollars", 5.0))

    prev_count = int(last_trade.get("count", 0))
    count = prev_count if prev_count > 0 else int(risk_amount / max(0.01, price))
    while count > 0 and (count * price + kalshi_order_fee(price, count)) > (risk_amount * 1.5 if prev_count > 0 else risk_amount):
        count -= 1
    if count < 1:
        count = 1

    trade_id = str(uuid.uuid4())
    now_est = datetime.datetime.now(ZoneInfo("America/New_York")).isoformat()

    trade_rec = {
        "id": trade_id,
        "mode": mode,
        "direction": opposite_side,
        "side": opposite_side,
        "entry_price": price,
        "count": count,
        "timestamp": now_est,
        "status": "OPEN",
        "pnl": 0.0,
        "reason": "REVERSAL",
        "ticker": market.get("ticker"),
        "trading_style": current_user.get("trading_style", "AUTO"),
        "signal_source": current_user.get("signal_source", "BLEND"),
        "is_reversal": True,
        "is_reverse": True,
        "strike": market.get("target_price") or market.get("strike_price") or market.get("floor_strike"),
        "market_snapshot": json.dumps(market)
    }

    # 6. Execute order (LIVE or PAPER)
    if mode == "LIVE":
        priv = decrypt_kalshi_key(current_user.get('kalshi_priv_key_encrypted', ''))
        if not priv:
            raise HTTPException(status_code=400, detail="Invalid kalshi keys for live reversal.")
        kt = KalshiTrader(key_id=current_user.get('kalshi_key_id'), private_key_pem=priv)
        if not kt.is_authenticated():
            raise HTTPException(status_code=400, detail="Kalshi authentication failed.")

        bal_res = kt.get_balance()
        if bal_res.get('success'):
            avail_bal = float(bal_res.get('balance_dollars', 0.0))
            order_cost = count * price
            if avail_bal < order_cost:
                raise HTTPException(status_code=400, detail=f"Insufficient live balance (${avail_bal:.2f}) for reversal (${order_cost:.2f}).")

        res = kt.place_order(
            ticker=market.get("ticker"),
            side="yes" if opposite_side == "YES" else "no",
            count=count,
            limit_price_dollars=price,
            dry_run=False
        )
        if not res.get("success"):
            raise HTTPException(status_code=400, detail=f"Live order failed: {res.get('error')}")

        trade_rec["entry_price"] = float(res.get("filled_price", price))
        trade_rec["id"] = str(res.get("client_order_id", trade_id))
        trade_rec["count"] = _filled_count(res, count)
    else:
        # Paper
        cost = count * price + kalshi_order_fee(price, count)
        if not deduct_user_paper_balance(user_id, cost):
            avail_bal = float(current_user.get("paper_balance", 500.0))
            raise HTTPException(status_code=400, detail=f"Insufficient paper balance for reversal. Cost: ${cost:.2f}, Bal: ${avail_bal:.2f}")

    TradeStore.insert_trade(user_id, trade_rec)

    with _live_balance_lock:
        _live_balance_cache.pop(user_id, None)

    return {"success": True, "side": opposite_side, "count": count, "price": trade_rec["entry_price"]}


def get_optional_user(
    authorization: Optional[str] = Header(None),
    saas_token: Optional[str] = Cookie(None)
):
    """Extract authenticated user if bearer token or cookie is provided, otherwise return None."""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    elif saas_token:
        token = saas_token

    if not token:
        return None
    try:
        payload = decode_jwt_token(token)
        if not payload or not payload.get("user_id"):
            return None
        return get_user_by_id(payload["user_id"])
    except (ValueError, TypeError, KeyError) as e:
        logger.warning(f"Failed to get optional user: {e}")
        return None


@router.get("/community")
def get_community_leaderboard(current_user: Optional[dict] = Depends(get_optional_user)):
    """
    Public / Authenticated Social Community Leaderboard.
    Aggregates active user profiles with sanitized trading performance stats:
    win rate, net PnL, trade counts, trading style, and ranking.
    Sensitive data (passwords, private keys, API key IDs) is strictly excluded.
    """

    active_users = get_all_active_users()
    requesting_user_id = current_user.get("id") if current_user else None

    users_data = []
    total_trades_all = 0
    total_wins_all = 0
    total_closed_all = 0

    for u in active_users:
        uid = u["id"]

        # All-time stats from SQL (not limited to the most recent trades)
        open_list = TradeStore.get_open_trades(uid)
        open_trades = len(open_list)
        st = TradeStore.get_closed_stats(uid)
        ps, ls = st.get("PAPER", {}), st.get("LIVE", {})
        paper_wins, paper_losses = int(ps.get("wins", 0)), int(ps.get("losses", 0))
        live_wins, live_losses = int(ls.get("wins", 0)), int(ls.get("losses", 0))
        paper_closed_n, live_closed_n = int(ps.get("closed", 0)), int(ls.get("closed", 0))
        paper_net_pnl = round(float(ps.get("pnl", 0.0)), 2)
        live_net_pnl = round(float(ls.get("pnl", 0.0)), 2)
        paper_win_rate = round(paper_wins / paper_closed_n * 100, 1) if paper_closed_n else 0.0
        live_win_rate = round(live_wins / live_closed_n * 100, 1) if live_closed_n else 0.0

        wins = paper_wins + live_wins
        losses = paper_losses + live_losses
        closed_count = paper_closed_n + live_closed_n
        total_trades = closed_count + open_trades
        win_rate = round((wins / closed_count * 100), 1) if closed_count > 0 else 0.0
        net_pnl = round(paper_net_pnl + live_net_pnl, 2)
        avg_pnl = round(net_pnl / closed_count, 2) if closed_count > 0 else 0.0
        paper_trades_n = paper_closed_n + sum(1 for t in open_list if str(t.get("mode", "PAPER")).upper() == "PAPER")
        live_trades_n = live_closed_n + sum(1 for t in open_list if str(t.get("mode", "PAPER")).upper() == "LIVE")

        total_trades_all += total_trades
        total_wins_all += wins
        total_closed_all += closed_count

        uname = u.get("username", "Trader")
        initials = (uname[:2] if len(uname) >= 2 else uname).upper()
        strategy_perf = TradeStore.get_strategy_performance(uid)

        users_data.append({
            "id": uid,
            "username": uname,
            "profile_pic": u.get("profile_pic"),
            "initials": initials,
            "role": u.get("role", "user"),
            "target_asset": u.get("target_asset", "BTC"),
            "trading_style": u.get("trading_style", "AUTO"),
            "trading_mode": u.get("trading_mode", "PAPER"),
            "ai_enabled": bool(u.get("ai_enabled", 1)),
            "signal_source": u.get("signal_source", "RL_DQN"),
            "model_choice": u.get("model_choice", "RL_DQN"),
            "stop_loss_pct": u.get("stop_loss_pct", 50.0),
            "take_profit_pct": u.get("take_profit_pct", 50.0),
            "take_profit_enabled": bool(u.get("take_profit_enabled", 1)),
            "trailing_stop_enabled": bool(u.get("trailing_stop_enabled", 0)),
            "second_entry_enabled": bool(u.get("second_entry_enabled", 0)),
            "reentry_after_stop_loss": bool(u.get("reentry_after_stop_loss", 0)),
            "total_trades": total_trades,
            "open_trades": open_trades,
            "closed_trades": closed_count,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "net_pnl": net_pnl,
            "avg_pnl": avg_pnl,
            "strategy_performance": strategy_perf,
            "paper_trades": paper_trades_n,
            "paper_wins": paper_wins,
            "paper_losses": paper_losses,
            "paper_win_rate": paper_win_rate,
            "paper_net_pnl": paper_net_pnl,
            "live_trades": live_trades_n,
            "live_wins": live_wins,
            "live_losses": live_losses,
            "live_win_rate": live_win_rate,
            "live_net_pnl": live_net_pnl,
            "is_self": bool(requesting_user_id and requesting_user_id == uid)
        })

    # Sort default by Net PnL descending, then win rate, then total trades
    users_data.sort(key=lambda x: (x["net_pnl"], x["win_rate"], x["total_trades"]), reverse=True)

    for idx, usr in enumerate(users_data, start=1):
        usr["rank"] = idx

    top_trader = users_data[0]["username"] if users_data else None
    top_pnl = users_data[0]["net_pnl"] if users_data else 0.0
    community_win_rate = round((total_wins_all / total_closed_all * 100), 1) if total_closed_all > 0 else 0.0

    total_live_pnl = round(sum(u.get("live_net_pnl", 0.0) for u in users_data), 2)
    total_paper_pnl = round(sum(u.get("paper_net_pnl", 0.0) for u in users_data), 2)
    total_live_trades = sum(u.get("live_trades", 0) for u in users_data)
    total_paper_trades = sum(u.get("paper_trades", 0) for u in users_data)

    return {
        "success": True,
        "summary": {
            "total_traders": len(users_data),
            "total_trades": total_trades_all,
            "community_win_rate": community_win_rate,
            "top_trader": top_trader,
            "top_pnl": top_pnl,
            "total_live_pnl": total_live_pnl,
            "total_paper_pnl": total_paper_pnl,
            "total_live_trades": total_live_trades,
            "total_paper_trades": total_paper_trades
        },
        "users": users_data
    }


@router.post("/user/reset_paper_balance")
@router.post("/paper/balance/reset")
def reset_current_user_paper_balance_endpoint(current_user: dict = Depends(get_current_user)):
    """Reset the current authenticated user's paper trading balance to $500.00 and clear paper PnL."""
    user_id = current_user["id"]
    success = reset_user_paper_balance_and_pnl(user_id, balance=500.0)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to reset paper balance.")
    return {
        "success": True,
        "message": "Paper balance and PnL reset to $500.00",
        "user_id": user_id,
        "paper_balance": 500.0,
        "total_pnl": 0.0
    }


@router.post("/community/copy_settings/{target_user_id}")
@router.post("/social/copy_settings/{target_user_id}")
def copy_community_user_settings(
    target_user_id: int, 
    current_user: dict = Depends(get_current_user)
):
    """
    Copy all trading strategy, risk limits, and AI model settings from target_user_id
    to the current authenticated user's account.
    Trade size (trade_size_dollars and trade_size_pct) is STRICTLY PRESERVED on the caller's account.
    """

    caller_id = current_user["id"]
    if int(caller_id) == int(target_user_id):
        raise HTTPException(status_code=400, detail="Cannot copy settings from your own account.")

    source_user = get_user_by_id(target_user_id)
    if not source_user:
        raise HTTPException(status_code=404, detail="Target trader not found.")

    try:
        result = copy_user_settings(source_user_id=target_user_id, target_user_id=caller_id)
    except ValueError as ve:
        logger.warning(f"ValueError while copying settings: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except (sqlite3.OperationalError, KeyError, TypeError) as e:
        logger.error(f"Database/Type error copying settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to copy settings: {str(e)}")

    return {
        "success": True,
        "message": f"Successfully copied strategy and settings from @{source_user['username']}! (Trade size preserved)",
        "result": result
    }


_COMMUNITY_REACTIONS: Dict[str, Dict[str, int]] = {}

class ReactionRequest(BaseModel):
    trade_id: str
    reaction: str

@router.get("/community/activity")
def get_community_activity():
    """Returns recent notable trades across all community members for the Battle Tape ticker."""
    activity = TradeStore.get_community_activity(limit=25)
    for a in activity:
        tid = a["trade_id"]
        a["reactions"] = _COMMUNITY_REACTIONS.get(tid, {})
    return {"success": True, "activity": activity}

@router.post("/community/react")
def post_community_reaction(req: ReactionRequest, current_user: Optional[dict] = Depends(get_optional_user)):
    """Add a reaction (e.g. 🔥, 🚀, 💀, 🍿, 🫡) to a community trade."""
    allowed = ["🔥", "🚀", "💀", "🍿", "🫡"]
    if req.reaction not in allowed:
        raise HTTPException(status_code=400, detail="Invalid reaction emoji.")
    if req.trade_id not in _COMMUNITY_REACTIONS:
        _COMMUNITY_REACTIONS[req.trade_id] = {emoji: 0 for emoji in allowed}
    _COMMUNITY_REACTIONS[req.trade_id][req.reaction] = _COMMUNITY_REACTIONS[req.trade_id].get(req.reaction, 0) + 1
    return {
        "success": True,
        "trade_id": req.trade_id,
        "reaction": req.reaction,
        "count": _COMMUNITY_REACTIONS[req.trade_id][req.reaction],
        "reactions": _COMMUNITY_REACTIONS[req.trade_id]
    }

@router.get("/user/equity")
def get_user_equity_curve(current_user: dict = Depends(get_current_user)):
    """Returns the cumulative equity curve points and drawdown statistics for the user."""
    equity = TradeStore.get_equity_curve(current_user["id"], limit=120)
    return {"success": True, "equity": equity}

@router.get("/user/quests")
def get_user_quests(current_user: dict = Depends(get_current_user)):
    """Returns daily quests, current XP, level, and earned achievement badges."""
    quests = TradeStore.get_user_quests_and_badges(current_user["id"])
    return {"success": True, "quests": quests}



class TicketRequest(BaseModel):
    issue_text: str

@router.post("/tickets")
def create_ticket(req: TicketRequest, current_user: dict = Depends(get_current_user)):

    conn = get_db_connection()
    now_est = datetime.datetime.now(ZoneInfo("America/New_York")).isoformat()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO support_tickets (user_id, username, issue_text, created_at)
            VALUES (?, ?, ?, ?)
        """, (current_user['id'], current_user['username'], req.issue_text, now_est))
        conn.commit()
        return {"success": True, "message": "Ticket submitted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ProfileRequest(BaseModel):
    profile_name: str
    settings_json: str

@router.get("/profiles")
def get_profiles(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, profile_name, settings_json, created_at FROM user_profiles WHERE user_id = ? ORDER BY id DESC", (current_user['id'],))
    profiles = [dict(r) for r in cursor.fetchall()]
    return {"success": True, "profiles": profiles}

@router.post("/profiles")
def create_profile(req: ProfileRequest, current_user: dict = Depends(get_current_user)):

    conn = get_db_connection()
    now_est = datetime.datetime.now(ZoneInfo("America/New_York")).isoformat()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_profiles (user_id, profile_name, settings_json, created_at)
            VALUES (?, ?, ?, ?)
        """, (current_user['id'], req.profile_name, req.settings_json, now_est))
        conn.commit()
        return {"success": True, "message": "Profile saved."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/profiles/{profile_id}")
def delete_profile(profile_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_profiles WHERE id = ? AND user_id = ?", (profile_id, current_user['id']))
        conn.commit()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/kalshi/exchange_balances")
def get_kalshi_exchange_balances(current_user: dict = Depends(get_current_user)):
    """Fetch live per-exchange balance breakdown from Kalshi for the current user."""
    if not current_user.get('kalshi_key_id') or not current_user.get('kalshi_priv_key_encrypted'):
        return {
            "success": False,
            "error": "No Kalshi API credentials linked.",
            "total_balance": 0.0,
            "exchanges": []
        }
    priv = decrypt_kalshi_key(current_user['kalshi_priv_key_encrypted'])
    if not priv:
        raise HTTPException(status_code=400, detail="Could not decrypt Kalshi private key.")
    kt = KalshiTrader(key_id=current_user['kalshi_key_id'], private_key_pem=priv)
    if not kt.is_authenticated():
        raise HTTPException(status_code=400, detail="Kalshi authentication failed. Check your API credentials.")
    
    breakdown = kt.get_exchange_breakdown(force_refresh=True)
    return breakdown

@router.post("/kalshi/transfer")
def transfer_kalshi_exchange_funds(req: ExchangeTransferRequest, current_user: dict = Depends(get_current_user)):
    """Transfer funds between Kalshi exchange matching engine shards (e.g. Shard 0 -> Shard 2)."""
    if not current_user.get('kalshi_key_id') or not current_user.get('kalshi_priv_key_encrypted'):
        raise HTTPException(status_code=400, detail="No Kalshi API credentials linked. Please add your credentials in Settings.")
    priv = decrypt_kalshi_key(current_user['kalshi_priv_key_encrypted'])
    if not priv:
        raise HTTPException(status_code=400, detail="Could not decrypt Kalshi private key.")
    kt = KalshiTrader(key_id=current_user['kalshi_key_id'], private_key_pem=priv)
    if not kt.is_authenticated():
        raise HTTPException(status_code=400, detail="Kalshi authentication failed.")
    
    res = kt.transfer_between_exchanges(
        source_exchange=req.source_exchange,
        destination_exchange=req.destination_exchange,
        amount_dollars=req.amount_dollars
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Transfer failed."))
    
    # Invalidate live balance cache
    user_id = current_user["id"]
    with _live_balance_lock:
        _live_balance_cache.pop(user_id, None)
        
    return res


from backend.database.trade_store import daily_limit_reason
import json as _json
from backend.database.trade_store import _trade_epoch
from backend.btc.auto_executor.saas_broadcaster import SIGNAL_SNAPSHOT_PATH, _snapshot_key
from backend.btc.kalshi_client import get_kalshi_15m_market
from backend.database.trade_store import TradeStore
from backend.btc.fees import entry_edge_cents
from backend.auth.security import decrypt_kalshi_key
from backend.btc.kalshi_trader import KalshiTrader
from backend.database.models import update_user_trading_mode


# Allowed profile picture types: extension -> media type. Files are re-validated by
# their magic bytes, so an .html/.svg/script upload can never be stored or served.
PROFILE_PIC_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                     ".gi": "image/gi", ".webp": "image/webp"}
PROFILE_PIC_MAX_BYTES = 15 * 1024 * 1024   # phone photos are often 3-8 MB; they are shrunk below
PROFILE_PIC_SIZE = 256                      # stored avatars are 256x256
PROFILE_PIC_MIN_SIDE = 32

# HEIC/HEIF (iPhone and Mac photos) are read through the optional pillow-heif package:
#   .venv\Scripts\python.exe -m pip install pillow-heif
try:
    from pillow_heif import register_heif_opener as _register_heif_opener
    _register_heif_opener()
    HEIF_SUPPORTED = True
except Exception:  # not installed (or failed to load) -> HEIC uploads get a clear message
    HEIF_SUPPORTED = False

_HEIF_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"hevm", b"hevs", b"mif1", b"msf1"}


def _sniff_image_ext(head: bytes):
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if head.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return ".gi"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    if head[4:8] == b"ftyp" and head[8:12] in _HEIF_BRANDS:
        return ".heic"
    return None


def _make_avatar(data: bytes):
    """Decode an uploaded image and return (bytes, ext) for a square avatar.
    If it's an animated GIF/WEBP, we keep it animated by bypassing the static crop."""

    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(data))
    
    # If it's an animated GIF or WEBP, keep it animated by bypassing the static crop
    is_animated = getattr(img, "is_animated", False)
    if is_animated and img.format in ("GIF", "WEBP"):
        ext = ".gi" if img.format == "GIF" else ".webp"
        return data, ext

    img.seek(0)                        # first frame of animated GIF/WebP
    img = ImageOps.exif_transpose(img)  # phone photos store rotation in EXIF
    if min(img.size) < PROFILE_PIC_MIN_SIDE:
        raise ValueError("too_small")
    img = ImageOps.fit(img, (PROFILE_PIC_SIZE, PROFILE_PIC_SIZE), method=Image.Resampling.LANCZOS)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    out = io.BytesIO()
    img.save(out, format="WEBP", quality=85)
    return out.getvalue(), ".webp"

@router.post("/profile/picture")
async def upload_profile_picture(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):


    data = await file.read(PROFILE_PIC_MAX_BYTES + 1)
    if len(data) > PROFILE_PIC_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 15 MB).")
    kind = _sniff_image_ext(data[:16])
    if kind is None:
        raise HTTPException(status_code=400, detail="Please choose a JPEG, PNG, GIF, WebP or HEIC photo.")
    if kind == ".heic" and not HEIF_SUPPORTED:
        raise HTTPException(status_code=400, detail="HEIC photos aren't enabled on this server yet. Please pick a JPEG or PNG, or set iPhone Settings > Camera > Formats > Most Compatible.")
    try:
        avatar, ext = await run_in_threadpool(_make_avatar, data)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Image is too small (at least {PROFILE_PIC_MIN_SIDE}x{PROFILE_PIC_MIN_SIDE} pixels).")
    except Exception as e:
        logger.warning(f"[Profile] Unreadable image from user {current_user['id']}: {e}")
        raise HTTPException(status_code=400, detail="That file could not be read as an image.")

    profiles_dir = os.path.join(DATA_DIR, "profiles")
    os.makedirs(profiles_dir, exist_ok=True)
    # Remove any previous picture for this user (any extension)
    for old_ext in PROFILE_PIC_TYPES:
        old_path = os.path.join(profiles_dir, f"user_{current_user['id']}{old_ext}")
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass
    filename = f"user_{current_user['id']}{ext}"
    tmp_path = os.path.join(profiles_dir, filename + ".tmp")
    with open(tmp_path, "wb") as buffer:
        buffer.write(avatar)
    os.replace(tmp_path, os.path.join(profiles_dir, filename))

    url = f"/profiles/{filename}?v={int(time.time())}"
    conn = get_db_connection()
    try:
        conn.execute("UPDATE users SET profile_pic = ? WHERE id = ?", (url, current_user['id']))
        conn.commit()
    except Exception as e:
        logger.error(f"[Profile] Could not save profile picture for user {current_user['id']}: {e}")
        raise HTTPException(status_code=500, detail="Could not save profile picture.")
    return {"success": True, "url": url}




# ── Web push (trade-won alerts). These used to be registered as /api/auth/api/push/...
# while the page called /api/push/..., and saving crashed (int() of the user dict), so no
# subscription was ever stored. The page now calls /api/auth/push/*.
@router.get("/push/public_key")
def get_vapid_public_key(current_user: dict = Depends(get_current_user)):
    return {"public_key": vapid_public_key()}


@router.post("/push/subscribe")
def subscribe_push(sub: dict, current_user: dict = Depends(get_current_user)):
    if not save_subscription(current_user["id"], sub):
        raise HTTPException(status_code=400, detail="Invalid push subscription.")
    return {"success": True}


@router.get("/push/status")
def push_status(current_user: dict = Depends(get_current_user)):

    return {"success": True, "subscribed": has_subscription(current_user["id"]),
            "configured": bool(vapid_public_key()),
            "notify_trade_results": bool(current_user.get("notify_trade_results", 1))}


@router.post("/push/test")
def push_test(current_user: dict = Depends(get_current_user)):
    if not has_subscription(current_user["id"]):
        raise HTTPException(status_code=400, detail="This device isn't subscribed yet. Tap 'Enable iOS/Web Alerts' first.")
    sent = send_web_push(current_user["id"], "Test notification ✅", "Trade alerts are working on this device.")
    if not sent:
        raise HTTPException(status_code=502, detail="The push service rejected the notification. Disable and re-enable alerts, then try again.")
    return {"success": True, "sent": sent}
@router.get('/trading_tip')
def get_trading_tip(current_user: dict = Depends(get_current_user)):
    trades = TradeStore.get_recent_trades(current_user['id'], limit=100)
    closed = [t for t in trades if t.get('status') != 'OPEN']
    wins = [t for t in closed if float(t.get('pnl', 0)) > 0]
    wr = len(wins) / len(closed) if closed else 0

    style = str(current_user.get('trading_style', 'AUTO')).upper()
    source = str(current_user.get('signal_source', 'BLEND')).upper()
    tp = float(current_user.get('take_profit_pct', 50.0))
    sl = float(current_user.get('stop_loss_pct', 100.0))
    
    tip = ''
    if source == 'RL_SCALPER':
        tip = 'You are running the experimental RL Scalper! Since it takes many fast trades, fees and slippage add up quickly. Keep your Stop Loss tight (around 8%) and Take Profit low (10-12%) to stay profitable.'
    elif style == 'PREDICTION' and sl > 50:
        tip = 'You are using PREDICTION style which forces trades regardless of market chop. Combined with a 100% stop loss, a single bad trade can wipe out multiple wins. Consider switching to AUTO or SNIPER, and tighten your stop loss to 15-20%.'
    elif style == 'CHOP' and tp > 30 and wr < 0.3:
        tip = 'Your CHOP style thrives in low volatility, but setting a Take Profit of 50% is too greedy for flat markets. Lower your Take Profit to 10-15% to secure quick range-bound wins.'
    elif style == 'MOMENTUM_SURFER' and tp > 40 and wr < 0.4:
        tip = 'Momentum Surfer catches fast breakouts, but your high 42% Take Profit might be missing exits before the momentum fades. Try lowering it to 20-25% to drastically improve your win rate.'
    elif tp < 8 and wr < 0.6:
        tip = 'Your Take Profit is extremely tight. While it secures quick wins, it means your winning trades do not pay enough to cover your Stop Loss losses. Try increasing Take Profit to 15-20% so your winners outweigh your losers!'
    else:
        tip = 'Your settings look solid! Keep monitoring your win rate and adjust your Stop Loss / Take Profit dynamically to adapt to changing market volatility.'

    return {'success': True, 'tip': tip}
