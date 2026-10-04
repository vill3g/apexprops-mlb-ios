import re
with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_fields = '''    xgb_estimators: Optional[int] = None
    xgb_max_depth: Optional[int] = None
    trading_universe: Optional[str] = None
    min_sports_confidence: Optional[float] = None'''

code = code.replace('    xgb_estimators: Optional[int] = None\n    xgb_max_depth: Optional[int] = None', new_fields)

# Also update update_user_config call
new_args = '''        req.class_weight if req.class_weight is not None else current_user.get("class_weight", "balanced"),
        req.xgb_estimators if req.xgb_estimators is not None else current_user.get("xgb_estimators", 300),
        req.xgb_max_depth if req.xgb_max_depth is not None else current_user.get("xgb_max_depth", 5),
        req.trading_universe if req.trading_universe is not None else current_user.get("trading_universe", "FINANCIAL"),
        req.min_sports_confidence if req.min_sports_confidence is not None else current_user.get("min_sports_confidence", 70.0)
    )'''

code = re.sub(r'req\.class_weight if req\.class_weight is not None else current_user\.get\("class_weight", "balanced"\),\s*req\.xgb_estimators if req\.xgb_estimators is not None else current_user\.get\("xgb_estimators", 300\),\s*req\.xgb_max_depth if req\.xgb_max_depth is not None else current_user\.get\("xgb_max_depth", 5\)\s*\)', new_args, code)

with open('backend/auth/routes.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Updated routes.py')
