import re

routes_path = "backend/routes/engine.py"
with open(routes_path, "r", encoding="utf-8") as f:
    code = f.read()

code = re.sub(r'(take_profit_pct=float\(data\.get\("take_profit_pct", 50\.0\)\),)', r'\1\n                take_profit_enabled=bool(data.get("take_profit_enabled", True)),', code)

with open(routes_path, "w", encoding="utf-8") as f:
    f.write(code)
print("Updated engine.py!")
