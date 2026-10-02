import re

path = "backend/btc/auto_executor/settlement.py"
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

target = '                        newly_settled_count += 1'
replacement = target + """
                        if is_win:
                            u = get_user_by_id(user_id) if user_id else None
                            if u and u.get('notify_trade_results', 1):
                                send_web_push(user_id, 'Trade Won! \U0001F389', f'+${t["pnl"]:.2f} profit on {t.get("ticker", "Kalshi")}')"""

code = code.replace(target, replacement)

with open(path, "w", encoding="utf-8") as f:
    f.write(code)
