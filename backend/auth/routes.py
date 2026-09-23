from fastapi import APIRouter, HTTPException, Depends, Header

from pydantic import BaseModel
class TradingModeRequest(BaseModel):
    mode: str

class ManualTradeRequest(BaseModel):
    direction: str
    amount_dollars: float

class UserConfigRequest(BaseModel):
    trade_size_dollars: float
    stop_loss_pct: float
    one_click_trade: bool
    auto_force_trade: bool = False
    trading_style: str = "AUTO"
    signal_source: str = "ML_ENSEMBLE"
    take_profit_pct: float = 50.0
    max_daily_trades: int = 10
    max_daily_risk: float = 50.0
    trailing_stop_enabled: bool = False
    trailing_stop_activation_pct: float = 35.0
    trailing_stop_distance_pct: float = 6.0
    # New Admin-Level ML Controls
    model_choice: str = "Swarm"
    train_window: int = 4000
    regularization_c: float = 0.5
    class_weight: str = "balanced"
    xgb_estimators: int = 300
    xgb_max_depth: int = 5
    xgb_learning_rate: float = 0.1
    ignore_pass_technical: bool = False
    one_shot_ai: bool = False

from typing import Optional
from backend.database.models import create_user, get_user_by_username, update_user_kalshi_keys, get_user_by_id
from backend.auth.security import hash_password, verify_password, create_jwt_token, decode_jwt_token, encrypt_kalshi_key, INVITE_CODE

router = APIRouter(prefix="/api/auth", tags=["auth"])

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

def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ")[1]
    payload = decode_jwt_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = get_user_by_id(payload['user_id'])
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return user

@router.post("/register")
def register(req: RegisterRequest):
    if req.invite_code != INVITE_CODE:
        raise HTTPException(status_code=403, detail="Invalid invite code.")
    
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password too short.")
        
    hashed = hash_password(req.password)
    user_id = create_user(req.username, hashed)
    if not user_id:
        raise HTTPException(status_code=400, detail="Username already exists.")
        
    token = create_jwt_token(user_id, req.username)
    return {"success": True, "token": token, "username": req.username}

@router.post("/login")
def login(req: LoginRequest):
    user = get_user_by_username(req.username)
    if not user or not verify_password(req.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
        
    token = create_jwt_token(user['id'], user['username'])
    return {"success": True, "token": token, "username": user['username']}

@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "success": True, 
        "user_id": current_user['id'],
        "username": current_user['username'],
        "trading_mode": current_user.get("trading_mode", "PAPER"),
        "paper_balance": current_user.get("paper_balance", 500.0),
        "has_kalshi_keys": bool(current_user['kalshi_key_id'] and current_user['kalshi_priv_key_encrypted'])
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


@router.get("/dashboard_stats")
def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    import os, json
    from backend.database.models import DATA_DIR
    from backend.auth.security import decrypt_kalshi_key
    from backend.btc.kalshi_trader import KalshiTrader
    from backend.btc.kalshi_client import get_kalshi_15m_market
    
    user_id = current_user['id']
    hist_path = os.path.join(DATA_DIR, 'users', str(user_id), 'trades_history.json')
    
    trades = []
    if os.path.exists(hist_path):
        try:
            with open(hist_path, 'r') as f:
                trades = json.load(f)
        except Exception:
            pass
            
    trading_mode = current_user.get('trading_mode', 'PAPER')
    
    # Filter trades to only show stats/ledger for the active mode!
    trades_filtered = [t for t in trades if t.get('mode', 'PAPER') == trading_mode]
            
    wins = sum(1 for t in trades_filtered if float(t.get("pnl", 0)) > 0 and t.get("status") != "OPEN")
    losses = sum(1 for t in trades_filtered if float(t.get("pnl", 0)) < 0 and t.get("status") != "OPEN")
    total_pnl = sum(float(t.get("pnl", 0)) for t in trades_filtered if t.get("status") != "OPEN")
    
    market = get_kalshi_15m_market()
    live_open_pnl = 0.0
    open_paper_value = 0.0
    
    for t in trades_filtered:
        if t.get("status") == "OPEN":
            if market and market.get("status") == "active":
                side = t.get("side", "YES").upper()
                entry = t.get("entry_price", 0.5)
                count = t.get("count", 0)
                
                # If market ticker doesn't match, assume it expired and we're waiting for settle
                if market.get("ticker") != t.get("ticker"):
                    exit_price = entry # unchanged
                else:
                    exit_price = market.get("yes_bid", entry) if side == "YES" else market.get("no_bid", entry)
                    
                live_pnl = (exit_price - entry) * count
                t["live_pnl"] = live_pnl
                live_open_pnl += live_pnl
                
                if t.get("mode", "PAPER") == "PAPER":
                    open_paper_value += (count * exit_price)
            else:
                t["live_pnl"] = 0.0

    total_pnl += live_open_pnl
    
    balance_dollars = None
    if trading_mode == 'PAPER':
        balance_dollars = current_user.get("paper_balance", 500.0)
        balance_dollars = round(float(balance_dollars) + open_paper_value, 2)
    elif trading_mode == 'LIVE' and current_user.get('kalshi_key_id') and current_user.get('kalshi_priv_key_encrypted'):
        priv = decrypt_kalshi_key(current_user['kalshi_priv_key_encrypted'])
        if priv:
            kt = KalshiTrader(key_id=current_user['kalshi_key_id'], private_key_pem=priv)
            if kt.is_authenticated():
                bal = kt.get_balance()
                if bal.get('success'):
                    balance_dollars = round(bal.get('balance_dollars', 0.0) + (bal.get('portfolio_value', 0.0) / 100.0), 2)
                
    formatted_trades = []
    for t in trades[-50:][::-1]:
        # Parse time
        time_str = ""
        ts = t.get("timestamp")
        if isinstance(ts, (int, float)):
            import datetime
            time_str = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")
        elif isinstance(ts, str):
            # e.g. "2026-09-23 01:46:09 AM ET"
            try:
                parts = ts.split(" ")
                time_str = parts[1] + " " + parts[2]  # "01:46:09 AM"
            except:
                time_str = ts
        
        # Parse strike
        ticker = t.get("ticker", "")
        strike = t.get("strike")
        if not strike:
            if "-" in ticker:
                strike = ticker.split("-")[-1]
            else:
                strike = ticker
                
        # Parse PNL
        pnl = t.get("live_pnl", 0.0) if t.get("status") == "OPEN" else float(t.get("pnl", 0.0))
        
        formatted_trades.append({
            "id": t.get("id"),
            "time": time_str,
            "side": t.get("side", "").lower(),
            "strike": strike,
            "pnl_dollars": pnl,
            "status": t.get("status", "CLOSED"),
            "count": t.get("count", 0),
            "entry_price": t.get("entry_price", 0.0),
            "reason": t.get("reason", "AUTO"),
            "exit_reason": t.get("exit_reason", ""),
            "trading_style": t.get("trading_style", ""),
            "is_profit_reentry": t.get("is_profit_reentry", False),
            "is_reversal": t.get("is_reversal", False)
        })

    return {
        "success": True,
        "api_configured": bool(current_user.get('kalshi_key_id') and current_user.get('kalshi_priv_key_encrypted')),
        "balance_dollars": balance_dollars,
        "trading_mode": trading_mode,
        "ai_enabled": bool(current_user.get("ai_enabled", 1)),
        "trade_size_dollars": float(current_user.get("trade_size_dollars", 50.0)),
        "trading_style": current_user.get("trading_style", "AUTO"),
        "signal_source": current_user.get("signal_source", "ML_ENSEMBLE"),
        "stop_loss_pct": float(current_user.get("stop_loss_pct", 10.0)),
        "take_profit_pct": float(current_user.get("take_profit_pct", 50.0)),
        "max_daily_trades": int(current_user.get("max_daily_trades", 10)),
        "max_daily_risk": float(current_user.get("max_daily_risk", 50.0)),
        "trailing_stop_enabled": bool(current_user.get("trailing_stop_enabled", 0)),
        "trailing_stop_activation_pct": float(current_user.get("trailing_stop_activation_pct", 35.0)),
        "trailing_stop_distance_pct": float(current_user.get("trailing_stop_distance_pct", 6.0)),
        "one_click_trade": bool(current_user.get("one_click_trade", 0)),
        "auto_force_trade": bool(current_user.get("auto_force_trade", 0)),
        "total_pnl": round(total_pnl, 2),
        "win_rate": round((wins / (wins + losses)) * 100, 1) if (wins + losses) > 0 else 0.0,
        "wins": wins,
        "losses": losses,
        "recent_trades": formatted_trades
    }


@router.post("/trade/config")
def update_trade_config(req: TradingModeRequest, current_user: dict = Depends(get_current_user)):
    from backend.database.models import update_user_trading_mode
    mode = req.mode.upper()
    if mode not in ["LIVE", "PAPER"]:
        raise HTTPException(status_code=400, detail="Invalid mode.")
    update_user_trading_mode(current_user["id"], mode)
    return {"success": True, "trading_mode": mode}

@router.post("/trade/manual")
def manual_trade(req: ManualTradeRequest, current_user: dict = Depends(get_current_user)):
    import time
    import os
    from backend.database.models import DATA_DIR, update_user_paper_balance
    from backend.auth.security import decrypt_kalshi_key
    from backend.btc.kalshi_trader import KalshiTrader
    from backend.btc.kalshi_client import get_kalshi_15m_market
    import json
    
    amount = req.amount_dollars
    side = req.direction.upper()
    mode = current_user.get('trading_mode', 'PAPER')
    user_id = current_user["id"]
    
    if side not in ["YES", "NO"]:
        raise HTTPException(status_code=400, detail="Direction must be YES or NO")
        
    market = get_kalshi_15m_market()
    if not market or market.get("status") != "active":
        raise HTTPException(status_code=400, detail="No active market right now.")
        
    price = market.get("yes_ask", 0.5) if side == "YES" else market.get("no_ask", 0.5)
    count = int(amount / price)
    if count < 1:
        raise HTTPException(status_code=400, detail="Amount too low to buy 1 contract.")
        
    # Build trade record
    import uuid
    from datetime import datetime
    import pytz
    
    trade_id = str(uuid.uuid4())
    est_tz = pytz.timezone('US/Eastern')
    now_est = datetime.now(est_tz).strftime('%Y-%m-%d %I:%M:%S %p ET')
    
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
        "ticker": market.get("ticker")
    }
    
    # Save to JSON
    hist_path = os.path.join(DATA_DIR, 'users', str(user_id), 'trades_history.json')
    trades = []
    if os.path.exists(hist_path):
        with open(hist_path, 'r') as f:
            try: trades = json.load(f)
            except: pass
    
    if mode == "LIVE":
        priv = decrypt_kalshi_key(current_user['kalshi_priv_key_encrypted'])
        if not priv: raise HTTPException(status_code=400, detail="Invalid kalshi keys.")
        kt = KalshiTrader(key_id=current_user['kalshi_key_id'], private_key_pem=priv)
        if not kt.is_authenticated(): raise HTTPException(status_code=400, detail="Failed to auth with Kalshi.")
        
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
            
    else:
        # Paper trade
        curr_bal = current_user.get("paper_balance", 500.0)
        cost = count * price
        if curr_bal < cost:
            raise HTTPException(status_code=400, detail=f"Insufficient paper balance. Cost: ${cost:.2f}, Bal: ${curr_bal:.2f}")
        update_user_paper_balance(user_id, curr_bal - cost)
        
    trades.append(trade_rec)
    with open(hist_path, 'w') as f:
        json.dump(trades, f, indent=2)
        
    return {"success": True, "trade": trade_rec}



class AIToggleRequest(BaseModel):
    enabled: bool

@router.post("/ai_toggle")
def toggle_ai_signals(req: AIToggleRequest, current_user: dict = Depends(get_current_user)):
    from backend.database.models import update_user_ai_enabled
    update_user_ai_enabled(current_user["id"], req.enabled)
    return {"success": True, "ai_enabled": req.enabled}


@router.post("/trade/close_all")
def close_all_trades(current_user: dict = Depends(get_current_user)):
    import os, json
    from backend.database.models import DATA_DIR, update_user_paper_balance
    from backend.auth.security import decrypt_kalshi_key
    from backend.btc.kalshi_trader import KalshiTrader
    from backend.btc.kalshi_client import get_kalshi_15m_market
    
    user_id = current_user['id']
    mode = current_user.get('trading_mode', 'PAPER')
    hist_path = os.path.join(DATA_DIR, 'users', str(user_id), 'trades_history.json')
    
    trades = []
    if os.path.exists(hist_path):
        with open(hist_path, 'r') as f:
            try: trades = json.load(f)
            except: pass
            
    market = get_kalshi_15m_market()
    closed_count = 0
    
    # 1. LIVE Close
    if mode == 'LIVE':
        priv = decrypt_kalshi_key(current_user.get('kalshi_priv_key_encrypted', ''))
        if not priv: raise HTTPException(status_code=400, detail="Invalid kalshi keys.")
        kt = KalshiTrader(key_id=current_user.get('kalshi_key_id'), private_key_pem=priv)
        if not kt.is_authenticated(): raise HTTPException(status_code=400, detail="Failed to auth with Kalshi.")
        
        # Get live positions
        pos_resp = kt.get_positions()
        if pos_resp and pos_resp.get('success'):
            positions = pos_resp.get('positions', [])
            for p in positions:
                ticker = p.get('ticker')
                yes_pos = p.get('position_yes', 0)
                no_pos = p.get('position_no', 0)
                if yes_pos > 0:
                    kt.close_position(ticker=ticker, purchased_side="yes", count=yes_pos, dry_run=False)
                    closed_count += 1
                if no_pos > 0:
                    kt.close_position(ticker=ticker, purchased_side="no", count=no_pos, dry_run=False)
                    closed_count += 1
                    
        # Update JSON statuses
        for t in trades:
            if t.get("status") == "OPEN" and t.get("mode") == "LIVE":
                t["status"] = "CLOSED"
                t["reason"] = "MANUAL_CLOSE"
                
    # 2. PAPER Close
    else:
        avail_bal = float(current_user.get('paper_balance', 500.0))
        for t in trades:
            if t.get("status") == "OPEN" and t.get("mode", "PAPER") == "PAPER":
                entry = t.get("entry_price", 0.5)
                count = t.get("count", 0)
                side = t.get("side", "YES").upper()
                
                exit_price = entry # default to scratch
                if market and market.get("status") == "active" and market.get("ticker") == t.get("ticker"):
                    exit_price = market.get("yes_bid", entry) if side == "YES" else market.get("no_bid", entry)
                
                # Credit the paper balance
                credit = count * exit_price
                avail_bal += credit
                
                # Record PnL
                t["status"] = "CLOSED"
                t["reason"] = "MANUAL_CLOSE"
                t["pnl"] = (exit_price - entry) * count
                closed_count += 1
                
        from backend.database.models import update_user_paper_balance
        update_user_paper_balance(user_id, avail_bal)
        
    # Save ledger
    with open(hist_path, 'w') as f:
        json.dump(trades, f, indent=4)
        
    return {"success": True, "closed_count": closed_count}

@router.post("/trade/close/{trade_id}")
def close_individual_trade(trade_id: str, current_user: dict = Depends(get_current_user)):
    import os, json
    from backend.database.models import DATA_DIR, update_user_paper_balance, get_user_lock
    from backend.auth.security import decrypt_kalshi_key
    from backend.btc.kalshi_trader import KalshiTrader
    from backend.btc.kalshi_client import get_kalshi_15m_market
    
    user_id = current_user['id']
    mode = current_user.get('trading_mode', 'PAPER')
    hist_path = os.path.join(DATA_DIR, 'users', str(user_id), 'trades_history.json')
    
    with get_user_lock(user_id):
        trades = []
        if os.path.exists(hist_path):
            with open(hist_path, 'r') as f:
                try: trades = json.load(f)
                except: pass
                
        target_trade = next((t for t in trades if t.get('id') == trade_id and t.get('status') == 'OPEN'), None)
        if not target_trade:
            raise HTTPException(status_code=404, detail="Open trade not found.")
            
        if mode == 'LIVE':
            priv = decrypt_kalshi_key(current_user.get('kalshi_priv_key_encrypted', ''))
            if not priv: raise HTTPException(status_code=400, detail="Invalid kalshi keys.")
            kt = KalshiTrader(key_id=current_user.get('kalshi_key_id'), private_key_pem=priv)
            if not kt.is_authenticated(): raise HTTPException(status_code=400, detail="Failed to auth with Kalshi.")
            
            ticker = target_trade.get('ticker')
            side = target_trade.get('side', '').lower()
            count = int(target_trade.get('count', 0))
            if count > 0:
                # To close a position, we purchase the opposite side
                kt.close_position(ticker=ticker, purchased_side=side, count=count, dry_run=False)
                
            target_trade["status"] = "CLOSED"
            target_trade["reason"] = "MANUAL_CLOSE"
            
        else:
            market = get_kalshi_15m_market()
            entry = float(target_trade.get("entry_price", 0.5))
            count = int(target_trade.get("count", 0))
            side = target_trade.get("side", "YES").upper()
            
            exit_price = entry
            if market and market.get("status") == "active" and market.get("ticker") == target_trade.get("ticker"):
                exit_price = float(market.get("yes_bid", entry) if side == "YES" else market.get("no_bid", entry))
            
            credit = count * exit_price
            avail_bal = float(current_user.get('paper_balance', 500.0)) + credit
            update_user_paper_balance(user_id, avail_bal)
            
            target_trade["status"] = "CLOSED"
            target_trade["reason"] = "MANUAL_CLOSE"
            target_trade["pnl"] = (exit_price - entry) * count
            
        with open(hist_path, 'w') as f:
            json.dump(trades, f, indent=4)
            
    return {"success": True, "trade_id": trade_id}

@router.post("/user/config")
def set_user_config(req: UserConfigRequest, current_user: dict = Depends(get_current_user)):
    from backend.database.models import update_user_config
    update_user_config(
        current_user["id"], 
        req.trade_size_dollars, 
        req.stop_loss_pct, 
        req.one_click_trade, 
        req.auto_force_trade, 
        req.trading_style, 
        req.signal_source,
        req.take_profit_pct,
        req.max_daily_trades,
        req.max_daily_risk,
        req.trailing_stop_enabled,
        req.trailing_stop_activation_pct,
        req.trailing_stop_distance_pct,
        req.model_choice,
        req.train_window,
        req.regularization_c,
        req.class_weight,
        req.xgb_estimators,
        req.xgb_max_depth,
        req.xgb_learning_rate,
        req.ignore_pass_technical,
        req.one_shot_ai
    )
    
    # Immediately apply to current live engine memory
    from backend.main import get_auto_executor
    ex = get_auto_executor("BTC", guest_id=current_user["id"])
    new_settings = ex.ai_settings.copy() if hasattr(ex, 'ai_settings') else {}
    new_settings["trade_size_dollars"] = req.trade_size_dollars
    new_settings["stop_loss_pct"] = req.stop_loss_pct
    new_settings["one_click_trade"] = req.one_click_trade
    new_settings["auto_force_trade"] = req.auto_force_trade
    new_settings["trading_style"] = req.trading_style
    new_settings["signal_source"] = req.signal_source
    new_settings["take_profit_pct"] = req.take_profit_pct
    new_settings["max_daily_trades"] = req.max_daily_trades
    new_settings["max_daily_risk"] = req.max_daily_risk
    new_settings["trailing_stop_enabled"] = req.trailing_stop_enabled
    new_settings["trailing_stop_activation_pct"] = req.trailing_stop_activation_pct
    new_settings["trailing_stop_distance_pct"] = req.trailing_stop_distance_pct
    
    new_settings["model_choice"] = req.model_choice
    new_settings["train_window"] = req.train_window
    new_settings["regularization_c"] = req.regularization_c
    new_settings["class_weight"] = req.class_weight
    new_settings["xgb_estimators"] = req.xgb_estimators
    new_settings["xgb_max_depth"] = req.xgb_max_depth
    new_settings["xgb_learning_rate"] = req.xgb_learning_rate
    new_settings["ignore_pass_technical"] = req.ignore_pass_technical
    new_settings["one_shot_ai"] = req.one_shot_ai

    ex.set_ai_settings(new_settings)
    
    # Set the execution bounds directly on the executor instance
    ex.set_risk_limits(max_daily_risk=req.max_daily_risk, max_daily_trades=req.max_daily_trades)
    
    return {"success": True}

@router.post("/trade/force_ml")
def force_ml_trade(current_user: dict = Depends(get_current_user)):
    import time, os, uuid, json
    from backend.database.models import DATA_DIR, update_user_paper_balance
    from backend.auth.security import decrypt_kalshi_key
    from backend.btc.kalshi_trader import KalshiTrader
    from backend.btc.kalshi_client import get_kalshi_15m_market
    from backend.main import get_cached_btc_analysis
    
    # 1. Get ML Analysis
    try:
        _, analysis = get_cached_btc_analysis(asset="BTC", timeframe="15m")
    except Exception as e:
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
            raise HTTPException(status_code=400, detail="ML is currently NEUTRAL. No signal to copy.")
    # 2. Get Market
    market = get_kalshi_15m_market()
    if not market or market.get("status") != "active":
        raise HTTPException(status_code=400, detail="No active market found.")
        
    price = market.get("yes_ask" if direction == "YES" else "no_ask")
    if not price or price <= 0:
        raise HTTPException(status_code=400, detail="Could not get executable price.")
        
    mode = current_user.get("trading_mode", "PAPER")
    user_id = current_user["id"]
    trade_size_pct = float(current_user.get("trade_size_pct", 20.0)) / 100.0
    
    trade_id = str(uuid.uuid4())
    count = 0
    
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
        if avail_bal < 1.0:
            raise HTTPException(status_code=400, detail="Insufficient live balance.")
            
        risk_amount = avail_bal * trade_size_pct
        count = max(1, int(risk_amount / max(0.01, price)))
        
        res = kt.place_order(
            ticker=market.get("ticker"),
            side="yes" if direction=="YES" else "no",
            count=count,
            limit_price_dollars=price,
            dry_run=False
        )
        if not res.get('success'):
            raise HTTPException(status_code=400, detail=f"Order failed: {res.get('error')}")
            
    else:
        # PAPER
        avail_bal = float(current_user.get('paper_balance', 500.0))
        if avail_bal < 1.0:
            raise HTTPException(status_code=400, detail="Insufficient paper balance.")
        risk_amount = avail_bal * trade_size_pct
        count = max(1, int(risk_amount / max(0.01, price)))
        cost = count * price
        if cost > avail_bal:
            raise HTTPException(status_code=400, detail="Insufficient paper balance for trade size.")
        update_user_paper_balance(user_id, avail_bal - cost)

    # 4. Save to ledger
    hist_path = os.path.join(DATA_DIR, 'users', str(user_id), 'trades_history.json')
    history = []
    if os.path.exists(hist_path):
        try:
            with open(hist_path, 'r') as f:
                history = json.load(f)
        except: pass
        
    history.append({
        "id": trade_id,
        "ticker": market.get("ticker"),
        "side": direction,
        "count": count,
        "entry_price": price,
        "status": "OPEN",
        "timestamp": time.time(),
        "mode": mode,
        "reason": "FORCE_ML_COPY"
    })
    
    with open(hist_path, 'w') as f:
        json.dump(history, f, indent=4)
        
    return {"success": True, "count": count, "side": direction, "price": price}
