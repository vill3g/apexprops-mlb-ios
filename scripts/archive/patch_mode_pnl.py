with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    c = f.read()

import re

# We need to find `get_dashboard_stats`
# and insert `trading_mode = current_user.get('trading_mode', 'PAPER')`
# and `trades = [t for t in trades if t.get('mode', 'PAPER') == trading_mode]`
# right before computing wins/losses.

old_block = """    trades = []
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
    open_paper_value = 0.0"""

new_block = """    trades = []
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
    open_paper_value = 0.0"""

# We also need to change `for t in trades:` to `for t in trades_filtered:` for the loop right below it!
# Wait, let's use regex to replace all `for t in trades:` in `get_dashboard_stats` up to the return statement.
# Instead of regex, let's do precise string replace.

old_loop = """    for t in trades:
        if t.get("status") == "OPEN":
            if market and market.get("status") == "active":"""

new_loop = """    for t in trades_filtered:
        if t.get("status") == "OPEN":
            if market and market.get("status") == "active":"""

# Next we have:
old_mode = """    trading_mode = current_user.get('trading_mode', 'PAPER')
    balance_dollars = current_user.get('paper_balance', 500.0) if trading_mode == 'PAPER' else None"""

new_mode = """    balance_dollars = current_user.get('paper_balance', 500.0) if trading_mode == 'PAPER' else None"""

old_return = """    return {
        "wins": wins,
        "losses": losses,
        "total_pnl": total_pnl,
        "balance_dollars": balance_dollars,
        "mode": trading_mode,
        "ai_enabled": current_user.get('ai_enabled', 1),
        "recent_trades": sorted(trades, key=lambda x: x.get('timestamp', ''), reverse=True)[:50]
    }"""

new_return = """    return {
        "wins": wins,
        "losses": losses,
        "total_pnl": total_pnl,
        "balance_dollars": balance_dollars,
        "mode": trading_mode,
        "ai_enabled": current_user.get('ai_enabled', 1),
        "recent_trades": sorted(trades_filtered, key=lambda x: x.get('timestamp', ''), reverse=True)[:50]
    }"""

c = c.replace(old_block, new_block)
c = c.replace(old_loop, new_loop)
c = c.replace(old_mode, new_mode)
c = c.replace(old_return, new_return)

with open('backend/auth/routes.py', 'w', encoding='utf-8') as f:
    f.write(c)
