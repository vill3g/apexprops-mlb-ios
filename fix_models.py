import re

model_path = "backend/database/models.py"
with open(model_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Add to USERS_SCHEMA
code = re.sub(r'("take_profit_pct": "REAL DEFAULT 50\.0",)', r'\1\n    "take_profit_enabled": "BOOLEAN DEFAULT 1",', code)

# 2. Add to allowed_cols
code = re.sub(r'("take_profit_pct",)', r'\1 "take_profit_enabled",', code)

# 3. Add to update_user_config definition
code = re.sub(r'(take_profit_pct: float = 50\.0,)', r'\1\n    take_profit_enabled: bool = True,', code)

# 4. Add to update_user_config SQL UPDATE
code = re.sub(r'(trading_style = \?, signal_source = \?, take_profit_pct = \?, max_daily_trades = \?,)', r'\1 take_profit_enabled = ?,', code)

# 5. Add to update_user_config values
code = re.sub(r'(trading_style, signal_source, take_profit_pct, max_daily_trades,)', r'\1 1 if take_profit_enabled else 0,', code)

# 6. Add to copy_fields
code = re.sub(r'("take_profit_pct": float\(source_user\.get\("take_profit_pct", 50\.0\)\),)', r'\1\n        "take_profit_enabled": int(bool(source_user.get("take_profit_enabled", 1))),', code)

with open(model_path, "w", encoding="utf-8") as f:
    f.write(code)
print("Updated models.py with take_profit_enabled!")
