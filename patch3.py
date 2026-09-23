import re

with open('backend/auth/routes.py', 'r') as f:
    content = f.read()

replacement = '''
    formatted_trades = []
    for t in trades_filtered[-50:][::-1]:
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
            "entry_price": t.get("entry_price", 0.0)
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
        "one_click_trade": bool(current_user.get("one_click_trade", 0)),
        "auto_force_trade": bool(current_user.get("auto_force_trade", 0)),
        "total_pnl": round(total_pnl, 2),
        "win_rate": round((wins / (wins + losses)) * 100, 1) if (wins + losses) > 0 else 0.0,
        "wins": wins,
        "losses": losses,
        "recent_trades": formatted_trades
    }
'''

# Find the return statement block in get_dashboard_stats
old_block_pattern = r'    return \{\s*"success": True,\s*"api_configured":.*?\s*"recent_trades": trades\[-50:\]\[::-1\]\s*\}'
content = re.sub(old_block_pattern, replacement.strip(), content, flags=re.DOTALL)

with open('backend/auth/routes.py', 'w') as f:
    f.write(content)
