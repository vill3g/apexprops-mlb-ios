import re

with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    c = f.read()

new_func = """@router.get("/dashboard_stats")
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
            
    wins = sum(1 for t in trades if float(t.get("pnl", 0)) > 0 and t.get("status") != "OPEN")
    losses = sum(1 for t in trades if float(t.get("pnl", 0)) < 0 and t.get("status") != "OPEN")
    total_pnl = sum(float(t.get("pnl", 0)) for t in trades if t.get("status") != "OPEN")
    
    market = get_kalshi_15m_market()
    live_open_pnl = 0.0
    open_paper_value = 0.0
    
    for t in trades:
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
    
    trading_mode = current_user.get('trading_mode', 'PAPER')
    balance_dollars = current_user.get('paper_balance', 500.0) if trading_mode == 'PAPER' else None
    
    if trading_mode == 'PAPER':
        balance_dollars = round(balance_dollars + open_paper_value, 2)
    elif trading_mode == 'LIVE' and current_user.get('kalshi_key_id') and current_user.get('kalshi_priv_key_encrypted'):
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
        "trading_mode": trading_mode,
        "ai_enabled": bool(current_user.get("ai_enabled", 1)),
        "total_pnl": round(total_pnl, 2),
        "win_rate": round((wins / (wins + losses)) * 100, 1) if (wins + losses) > 0 else 0.0,
        "wins": wins,
        "losses": losses,
        "recent_trades": trades[-50:][::-1]
    }
"""

start_idx = c.find('@router.get("/dashboard_stats")')
if start_idx != -1:
    end_idx = c.find('@router.post("/trade/config")', start_idx)
    if end_idx == -1: end_idx = len(c)
    
    c = c[:start_idx] + new_func + '\n\n' + c[end_idx:]
    with open('backend/auth/routes.py', 'w', encoding='utf-8') as f:
        f.write(c)
    print("Patched dashboard stats")
else:
    print("Not found")
