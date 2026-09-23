import re

with open('backend/auth/routes.py', 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.startswith('formatted_trades = []'):
        new_lines.append('    ' + line)
    elif line.startswith('for t in trades_filtered[-50:][::-1]:'):
        new_lines.append('    ' + line)
    elif line.startswith('    # Parse time'):
        new_lines.append('    ' + line)
    elif line.startswith('    time_str = ""'):
        new_lines.append('    ' + line)
    elif line.startswith('    ts = t.get("timestamp")'):
        new_lines.append('    ' + line)
    elif line.startswith('    if isinstance(ts, (int, float)):'):
        new_lines.append('    ' + line)
    elif line.startswith('        import datetime'):
        new_lines.append('    ' + line)
    elif line.startswith('        time_str = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")'):
        new_lines.append('    ' + line)
    elif line.startswith('    elif isinstance(ts, str):'):
        new_lines.append('    ' + line)
    elif line.startswith('        # e.g. "2026-09-23 01:46:09 AM ET"'):
        new_lines.append('    ' + line)
    elif line.startswith('        try:'):
        new_lines.append('    ' + line)
    elif line.startswith('            parts = ts.split(" ")'):
        new_lines.append('    ' + line)
    elif line.startswith('            time_str = parts[1] + " " + parts[2]  # "01:46:09 AM"'):
        new_lines.append('    ' + line)
    elif line.startswith('        except:'):
        new_lines.append('    ' + line)
    elif line.startswith('            time_str = ts'):
        new_lines.append('    ' + line)
    elif line.startswith('    # Parse strike'):
        new_lines.append('    ' + line)
    elif line.startswith('    ticker = t.get("ticker", "")'):
        new_lines.append('    ' + line)
    elif line.startswith('    strike = t.get("strike")'):
        new_lines.append('    ' + line)
    elif line.startswith('    if not strike:'):
        new_lines.append('    ' + line)
    elif line.startswith('        if "-" in ticker:'):
        new_lines.append('    ' + line)
    elif line.startswith('            strike = ticker.split("-")[-1]'):
        new_lines.append('    ' + line)
    elif line.startswith('        else:'):
        new_lines.append('    ' + line)
    elif line.startswith('            strike = ticker'):
        new_lines.append('    ' + line)
    elif line.startswith('    # Parse PNL'):
        new_lines.append('    ' + line)
    elif line.startswith('    pnl = t.get("live_pnl", 0.0) if t.get("status") == "OPEN" else float(t.get("pnl", 0.0))'):
        new_lines.append('    ' + line)
    elif line.startswith('    formatted_trades.append({'):
        new_lines.append('    ' + line)
    elif line.startswith('        "id": t.get("id"),'):
        new_lines.append('    ' + line)
    elif line.startswith('        "time": time_str,'):
        new_lines.append('    ' + line)
    elif line.startswith('        "side": t.get("side", "").lower(),'):
        new_lines.append('    ' + line)
    elif line.startswith('        "strike": strike,'):
        new_lines.append('    ' + line)
    elif line.startswith('        "pnl_dollars": pnl,'):
        new_lines.append('    ' + line)
    elif line.startswith('        "status": t.get("status", "CLOSED"),'):
        new_lines.append('    ' + line)
    elif line.startswith('        "count": t.get("count", 0),'):
        new_lines.append('    ' + line)
    elif line.startswith('        "entry_price": t.get("entry_price", 0.0)'):
        new_lines.append('    ' + line)
    elif line.startswith('    })'):
        new_lines.append('    ' + line)
    elif line.startswith('return {'):
        new_lines.append('    ' + line)
    elif line.startswith('    "success": True,'):
        new_lines.append('    ' + line)
    elif line.startswith('    "api_configured":'):
        new_lines.append('    ' + line)
    elif line.startswith('    "balance_dollars": balance_dollars,'):
        new_lines.append('    ' + line)
    elif line.startswith('    "trading_mode": trading_mode,'):
        new_lines.append('    ' + line)
    elif line.startswith('    "ai_enabled": bool(current_user.get("ai_enabled", 1)),'):
        new_lines.append('    ' + line)
    elif line.startswith('    "trade_size_dollars": float(current_user.get("trade_size_dollars", 50.0)),'):
        new_lines.append('    ' + line)
    elif line.startswith('    "trading_style": current_user.get("trading_style", "AUTO"),'):
        new_lines.append('    ' + line)
    elif line.startswith('    "signal_source": current_user.get("signal_source", "ML_ENSEMBLE"),'):
        new_lines.append('    ' + line)
    elif line.startswith('    "stop_loss_pct": float(current_user.get("stop_loss_pct", 10.0)),'):
        new_lines.append('    ' + line)
    elif line.startswith('    "one_click_trade": bool(current_user.get("one_click_trade", 0)),'):
        new_lines.append('    ' + line)
    elif line.startswith('    "auto_force_trade": bool(current_user.get("auto_force_trade", 0)),'):
        new_lines.append('    ' + line)
    elif line.startswith('    "total_pnl": round(total_pnl, 2),'):
        new_lines.append('    ' + line)
    elif line.startswith('    "win_rate": round((wins / (wins + losses)) * 100, 1) if (wins + losses) > 0 else 0.0,'):
        new_lines.append('    ' + line)
    elif line.startswith('    "wins": wins,'):
        new_lines.append('    ' + line)
    elif line.startswith('    "losses": losses,'):
        new_lines.append('    ' + line)
    elif line.startswith('    "recent_trades": formatted_trades'):
        new_lines.append('    ' + line)
    elif line.startswith('}'):
        new_lines.append('    ' + line)
    else:
        new_lines.append(line)

with open('backend/auth/routes.py', 'w') as f:
    f.writelines(new_lines)
