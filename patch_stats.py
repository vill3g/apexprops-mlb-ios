import re

with open("backend/auth/routes.py", "r", encoding="utf-8") as f:
    code = f.read()

# Currently: recent_trades = sorted(trades_filtered, key=lambda x: x.get('timestamp', ''), reverse=True)[:10]
# Change it to: recent_trades = sorted(trades, key=lambda x: x.get('timestamp', ''), reverse=True)[:10]

code = re.sub(
    r"recent_trades = sorted\(trades_filtered, key=lambda x: x\.get\('timestamp', ''\), reverse=True\)\[:10\]",
    r"recent_trades = sorted(trades, key=lambda x: x.get('timestamp', ''), reverse=True)[:10]",
    code
)

with open("backend/auth/routes.py", "w", encoding="utf-8") as f:
    f.write(code)
