import re

with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''        formatted_trades.append({
            "id": t.get("id"),
            "time": time_str,
            "side": t.get("side", "").lower(),
            "strike": strike,
            "pnl_dollars": pnl,
            "status": t.get("status", "CLOSED"),
            "count": t.get("count", 0),
            "entry_price": t.get("entry_price", 0.0)
        })'''

new_block = '''        formatted_trades.append({
            "id": t.get("id"),
            "time": time_str,
            "side": t.get("side", "").lower(),
            "strike": strike,
            "pnl_dollars": pnl,
            "status": t.get("status", "CLOSED"),
            "count": t.get("count", 0),
            "entry_price": t.get("entry_price", 0.0),
            "reason": t.get("reason", "AUTO")
        })'''

content = content.replace(old_block, new_block)

with open('backend/auth/routes.py', 'w', encoding='utf-8') as f:
    f.write(content)
