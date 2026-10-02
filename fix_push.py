import re

path = "backend/btc/auto_executor/settlement.py"
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

# I will replace the messy injection with a clean one at the end of the settlement logic.
# Wait, I'll just remove the injected push logic and re-insert it properly after t["settlement_pnl"] = settlement_pnl
code = code.replace("""                            if is_win:\n\n    \n                                u = get_user_by_id(user_id) if user_id else None\n\n    \n                                if u and u.get('notify_trade_results', 1):\n\n    \n                                    send_web_push(user_id, 'Trade Won! \U0001F389', f'+${settlement_pnl:.2f} profit on {t.get("ticker")}')\n""", "")

target = 't["settlement_pnl"] = settlement_pnl'
replacement = target + """
                            if is_win:
                                u = get_user_by_id(user_id) if user_id else None
                                if u and u.get('notify_trade_results', 1):
                                    send_web_push(user_id, 'Trade Won! \U0001F389', f'+${settlement_pnl:.2f} profit on {t.get("ticker", "Kalshi")}')"""

if "send_web_push(user_id" not in code:
    code = code.replace(target, replacement)

with open(path, "w", encoding="utf-8") as f:
    f.write(code)
