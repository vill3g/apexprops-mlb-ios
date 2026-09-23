import os

with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_route = """

@router.get("/dashboard_stats")
def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    import os, json
    from backend.database.models import DATA_DIR
    from backend.auth.security import decrypt_kalshi_key
    from backend.btc.kalshi_trader import KalshiTrader
    
    user_id = current_user['id']
    hist_path = os.path.join(DATA_DIR, 'users', str(user_id), 'trades_history.json')
    
    trades = []
    if os.path.exists(hist_path):
        try:
            with open(hist_path, 'r') as f:
                trades = json.load(f)
        except Exception:
            pass
            
    wins = sum(1 for t in trades if float(t.get("pnl", 0)) > 0 and t.get("status") != "OPEN")
    losses = sum(1 for t in trades if float(t.get("pnl", 0)) < 0 and t.get("status") != "OPEN")
    total_pnl = sum(float(t.get("pnl", 0)) for t in trades if t.get("status") != "OPEN")
    open_trades = [t for t in trades if t.get("status") == "OPEN"]
    
    win_rate = round((wins / (wins + losses)) * 100, 1) if (wins + losses) > 0 else 0.0
    
    balance_dollars = None
    if current_user.get('kalshi_key_id') and current_user.get('kalshi_priv_key_encrypted'):
        priv = decrypt_kalshi_key(current_user['kalshi_priv_key_encrypted'])
        if priv:
            kt = KalshiTrader(key_id=current_user['kalshi_key_id'], private_key_pem=priv)
            if kt.is_authenticated():
                bal = kt.get_balance()
                if bal.get('success'):
                    balance_dollars = round(bal.get('balance_dollars', 0.0) + (bal.get('portfolio_value', 0.0) / 100.0), 2)
                
    return {
        "success": True,
        "balance_dollars": balance_dollars,
        "total_pnl": round(total_pnl, 2),
        "win_rate": win_rate,
        "wins": wins,
        "losses": losses,
        "recent_trades": trades[-50:][::-1],
        "open_trades": open_trades
    }
"""

if 'get_dashboard_stats' not in content:
    with open('backend/auth/routes.py', 'a', encoding='utf-8') as f:
        f.write(new_route)
    print('Added dashboard_stats route')
else:
    print('Route already exists')
