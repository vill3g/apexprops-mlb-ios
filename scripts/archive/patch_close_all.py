import os

with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    c = f.read()

close_all_func = """@router.post("/trade/close_all")
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
        
        # Get live portfolio
        pf = kt.get_portfolio()
        if pf and pf.get('success'):
            positions = pf.get('positions', [])
            for p in positions:
                ticker = p.get('ticker')
                pos = p.get('position', 0)
                if pos > 0:
                    kt.place_order(ticker=ticker, action="sell", side="yes", count=pos)
                    closed_count += 1
                elif pos < 0:
                    kt.place_order(ticker=ticker, action="sell", side="no", count=abs(pos))
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
"""

if 'def close_all_trades' not in c:
    c += '\n\n' + close_all_func
    with open('backend/auth/routes.py', 'w', encoding='utf-8') as f:
        f.write(c)
    print("Added close all endpoint")
