import re

path = "backend/database/models.py"
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

# Add to REQUIRED_COLUMNS
req_cols_pattern = r'("one_shot_ai": "BOOLEAN DEFAULT 0",\s*)("profile_pic": "TEXT DEFAULT NULL",)'
req_cols_repl = r'\1\2\n    "notify_trade_results": "BOOLEAN DEFAULT 1",\n    "notify_market_trends": "BOOLEAN DEFAULT 1",'
code = re.sub(req_cols_pattern, req_cols_repl, code)

# Add to update_user_config signature
sig_pattern = r'(ignore_pass_technical: bool = False, \s*one_shot_ai: bool = False)'
sig_repl = r'\1,\n    notify_trade_results: bool = True,\n    notify_market_trends: bool = True'
code = re.sub(sig_pattern, sig_repl, code)

# Add to update_user_config SQL SET
sql_pattern = r'(ignore_pass_technical = \?, one_shot_ai = \?)'
sql_repl = r'\1, notify_trade_results = ?, notify_market_trends = ?'
code = re.sub(sql_pattern, sql_repl, code)

# Add to update_user_config SQL values
val_pattern = r'(1 if ignore_pass_technical else 0, 1 if one_shot_ai else 0, )(user_id)'
val_repl = r'\1 1 if notify_trade_results else 0, 1 if notify_market_trends else 0, \2'
code = re.sub(val_pattern, val_repl, code)

with open(path, "w", encoding="utf-8") as f:
    f.write(code)

print("Updated models.py for notifications")
