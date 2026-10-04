import re
with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Replace the last argument of update_user_config
old_end = '''        req.use_kelly_criterion if req.use_kelly_criterion is not None else bool(current_user.get("use_kelly_criterion", 0)),
    )'''
new_end = '''        req.use_kelly_criterion if req.use_kelly_criterion is not None else bool(current_user.get("use_kelly_criterion", 0)),
        req.trading_universe if req.trading_universe is not None else current_user.get("trading_universe", "FINANCIAL"),
        req.min_sports_confidence if req.min_sports_confidence is not None else float(current_user.get("min_sports_confidence", 70.0))
    )'''
code = code.replace(old_end, new_end)

with open('backend/auth/routes.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Updated update_user_config call in routes')
