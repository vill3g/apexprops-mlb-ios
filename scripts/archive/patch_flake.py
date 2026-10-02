import re

with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    c = f.read()

# Replace the specific broadcast line that is crashing
c = re.sub(
    r'self\._broadcast_trade_to_users\(current_interval_id, side, market_price, \{"prob": float\(analysis\.get\("probability_percent", 50\)\)\}\)',
    r'# SaaS broadcasting is now handled concurrently by evaluate_and_execute_saas_users()',
    c
)

with open('backend/btc/auto_executor.py', 'w', encoding='utf-8') as f:
    f.write(c)
