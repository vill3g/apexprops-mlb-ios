with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    c = f.read()

force_trade_code = """
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
        
    signal = analysis.get("signal", "HOLD")
    if signal not in ["BUY", "SELL"]:
        raise HTTPException(status_code=400, detail="ML is currently NEUTRAL. No signal to copy.")
        
    direction = "YES" if signal == "BUY" else "NO"
    
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
"""

c += force_trade_code

with open('backend/auth/routes.py', 'w', encoding='utf-8') as f:
    f.write(c)
