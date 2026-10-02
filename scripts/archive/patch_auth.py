import os
import re

with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update get_me
if '"trading_mode": current_user.get("trading_mode")' not in content:
    content = content.replace(
        '"username": current_user[\'username\'],\n        "has_kalshi_keys":',
        '"username": current_user[\'username\'],\n        "trading_mode": current_user.get("trading_mode", "PAPER"),\n        "paper_balance": current_user.get("paper_balance", 500.0),\n        "has_kalshi_keys":'
    )

# 2. Add imports for manual trades and settings
add_imports = """
from pydantic import BaseModel
class TradingModeRequest(BaseModel):
    mode: str

class ManualTradeRequest(BaseModel):
    direction: str
    amount_dollars: float
"""
if 'class TradingModeRequest' not in content:
    content = content.replace('from pydantic import BaseModel', add_imports)

# 3. Add new endpoints
new_endpoints = """

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
            action="buy",
            side="yes" if side=="YES" else "no",
            count=count,
            price_cents=int(price * 100),
            client_order_id=trade_id
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

"""
if '@router.post("/trade/manual")' not in content:
    content += new_endpoints
    
with open('backend/auth/routes.py', 'w', encoding='utf-8') as f:
    f.write(content)
