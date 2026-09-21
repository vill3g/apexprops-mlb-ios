import re

with open('backend/btc/shadow_executor.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace("res = kalshi_trader.get_market(ticker)", "res = kalshi_trader.get_market_result(ticker)")

with open('backend/btc/shadow_executor.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Patched get_market to get_market_result")
