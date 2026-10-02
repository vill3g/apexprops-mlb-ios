import re

with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    c = f.read()

old_ret = """    return {
        "success": True,
        "balance_dollars": balance_dollars,
        "trading_mode": trading_mode,
        "ai_enabled": bool(current_user.get("ai_enabled", 1)),
        "total_pnl": round(total_pnl, 2),
        "win_rate": round((wins / (wins + losses)) * 100, 1) if (wins + losses) > 0 else 0.0,
        "wins": wins,
        "losses": losses,
        "recent_trades": trades[-50:][::-1]
    }"""

new_ret = """    return {
        "success": True,
        "balance_dollars": balance_dollars,
        "trading_mode": trading_mode,
        "ai_enabled": bool(current_user.get("ai_enabled", 1)),
        "trade_size_pct": float(current_user.get("trade_size_pct", 20.0)),
        "stop_loss_pct": float(current_user.get("stop_loss_pct", 10.0)),
        "one_click_trade": bool(current_user.get("one_click_trade", 0)),
        "auto_force_trade": bool(current_user.get("auto_force_trade", 0)),
        "total_pnl": round(total_pnl, 2),
        "win_rate": round((wins / (wins + losses)) * 100, 1) if (wins + losses) > 0 else 0.0,
        "wins": wins,
        "losses": losses,
        "recent_trades": trades[-50:][::-1]
    }"""

if old_ret in c:
    c = c.replace(old_ret, new_ret)

with open('backend/auth/routes.py', 'w', encoding='utf-8') as f:
    f.write(c)
