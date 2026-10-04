import re

with open('backend/core/registry.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_set = 'SUPPORTED_ASSETS = {"BTC", "ETH", "GOLD", "NDQ", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "SOL", "DOGE"}'
new_set = 'SUPPORTED_ASSETS = {"BTC", "ETH", "GOLD", "NDQ", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "SOL", "DOGE", "NFL", "MLB", "NBA", "UFC"}'

code = code.replace(old_set, new_set)

with open('backend/core/registry.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Updated SUPPORTED_ASSETS')
