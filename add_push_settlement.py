import re

path = "backend/btc/auto_executor/settlement.py"
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

push_import = "\nfrom backend.core.push_notifications import send_web_push\nfrom backend.database.models import get_user_by_id\n"
if "send_web_push" not in code:
    code = code.replace("from backend.auth.security import decrypt_kalshi_key", "from backend.auth.security import decrypt_kalshi_key" + push_import)

# We want to send push right after t["status"] = "SETTLED" and t["result"] = "WIN" / "LOSS"
# It happens in two places: official_result resolution and legacy_exchange_candle resolution
def inject_push(match):
    prefix = match.group(1)
    status_line = match.group(2)
    return f"{prefix}{status_line}\n{prefix}if is_win:\n{prefix}    u = get_user_by_id(user_id) if user_id else None\n{prefix}    if u and u.get('notify_trade_results', 1):\n{prefix}        send_web_push(user_id, 'Trade Won! \U0001F389', f'+${{settlement_pnl:.2f}} profit on {{t.get(\"ticker\")}}')\n"

# First block
code = re.sub(r'(\s+)(t\["status"\] = "SETTLED"\s*\n\s*t\["result"\] = "WIN" if is_win else "LOSS")', inject_push, code)

with open(path, "w", encoding="utf-8") as f:
    f.write(code)
