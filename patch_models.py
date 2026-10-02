import re

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\backend\\database\\models.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add to REQUIRED_COLUMNS
content = content.replace('"stop_loss_pct": "REAL DEFAULT 50.0",', '"stop_loss_pct": "REAL DEFAULT 50.0",\n    "stop_loss_enabled": "BOOLEAN DEFAULT 1",')

# 2. Add to allowed_cols in admin_update_user
content = content.replace('"trade_size_dollars", "paper_trade_size_dollars", "stop_loss_pct", "take_profit_pct", "take_profit_enabled",', '"trade_size_dollars", "paper_trade_size_dollars", "stop_loss_pct", "stop_loss_enabled", "take_profit_pct", "take_profit_enabled",')

# 3. Add to update_user_settings args
content = re.sub(r'(stop_loss_pct: float,\s*one_click_trade: bool,)', r'stop_loss_pct: float, \n    stop_loss_enabled: bool, \n    one_click_trade: bool,', content)

# 4. Add to UPDATE statement
content = content.replace('SET trade_size_dollars = ?, paper_trade_size_dollars = ?, stop_loss_pct = ?, one_click_trade = ?, auto_force_trade = ?,', 'SET trade_size_dollars = ?, paper_trade_size_dollars = ?, stop_loss_pct = ?, stop_loss_enabled = ?, one_click_trade = ?, auto_force_trade = ?,')

# 5. Add to tuple
content = content.replace('trade_size_dollars, paper_trade_size_dollars, stop_loss_pct, 1 if one_click_trade else 0, 1 if auto_force_trade else 0,', 'trade_size_dollars, paper_trade_size_dollars, stop_loss_pct, 1 if stop_loss_enabled else 0, 1 if one_click_trade else 0, 1 if auto_force_trade else 0,')

# 6. Add to copy_fields in copy_user_settings
content = content.replace('"stop_loss_pct": float(source_user.get("stop_loss_pct", 50.0)),', '"stop_loss_pct": float(source_user.get("stop_loss_pct", 50.0)),\n        "stop_loss_enabled": int(bool(source_user.get("stop_loss_enabled", 1))),')

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\backend\\database\\models.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated models.py!")
