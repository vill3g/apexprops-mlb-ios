import re

with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''    balance_dollars = None
    if trading_mode == 'PAPER':
        from backend.btc.paper_balance import load_balance
        balance_dollars = load_balance(guest_id=str(user_id))
        balance_dollars = round(balance_dollars + open_paper_value, 2)
    elif trading_mode == 'LIVE' and current_user.get('kalshi_key_id') and current_user.get('kalshi_priv_key_encrypted'):'''

new_block = '''    balance_dollars = None
    if trading_mode == 'PAPER':
        balance_dollars = current_user.get("paper_balance", 500.0)
        balance_dollars = round(float(balance_dollars) + open_paper_value, 2)
    elif trading_mode == 'LIVE' and current_user.get('kalshi_key_id') and current_user.get('kalshi_priv_key_encrypted'):'''

content = content.replace(old_block, new_block)

with open('backend/auth/routes.py', 'w', encoding='utf-8') as f:
    f.write(content)
