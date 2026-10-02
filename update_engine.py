import re

path = "backend/routes/engine.py"
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

# Add to update_user_config caller in engine.py
call_pattern = r'(take_profit_enabled=bool\(data\.get\("take_profit_enabled", True\)\),)'
call_repl = r'\1\n                notify_trade_results=bool(data.get("notify_trade_results", True)),\n                notify_market_trends=bool(data.get("notify_market_trends", True)),'
code = re.sub(call_pattern, call_repl, code)

with open(path, "w", encoding="utf-8") as f:
    f.write(code)

print("Updated engine.py")
