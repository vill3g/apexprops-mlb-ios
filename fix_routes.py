import re

routes_path = "backend/auth/routes.py"
with open(routes_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Add to UserConfigUpdate
code = re.sub(r'(take_profit_pct: float = 50\.0)', r'\1\n    take_profit_enabled: bool = True', code)

# 2. Add to user dict return
code = re.sub(r'("take_profit_pct": float\(current_user\.get\("take_profit_pct", 50\.0\)\),)', r'\1\n        "take_profit_enabled": bool(current_user.get("take_profit_enabled", 1)),', code)

# 3. Add to _executeSaveUserConfig parameters in update_user_config call
code = re.sub(r'(req\.take_profit_pct,)', r'\1\n        req.take_profit_enabled,', code)

# 4. Add to create_profile settings
code = re.sub(r'(new_settings\["take_profit_pct"\] = req\.take_profit_pct)', r'\1\n    new_settings["take_profit_enabled"] = req.take_profit_enabled', code)

# 5. Add to export profile
code = re.sub(r'("take_profit_pct": u\.get\("take_profit_pct", 50\.0\),)', r'\1\n            "take_profit_enabled": bool(u.get("take_profit_enabled", 1)),', code)

with open(routes_path, "w", encoding="utf-8") as f:
    f.write(code)
print("Updated routes.py!")
