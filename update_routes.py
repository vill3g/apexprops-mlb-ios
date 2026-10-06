import re

with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update UserConfigRequest
old_class = '''    min_sports_confidence: Optional[float] = None'''
new_class = '''    min_sports_confidence: Optional[float] = None
    min_sports_edge: Optional[float] = None
    sports_max_wager: Optional[float] = None
    sports_include_live: Optional[bool] = None'''
if old_class in content:
    content = content.replace(old_class, new_class)
else:
    print("Could not find class definition")

# 2. Update set_user_config
old_func = '''        req.min_sports_confidence if req.min_sports_confidence is not None else float(current_user.get("min_sports_confidence", 70.0))
    )'''
new_func = '''        req.min_sports_confidence if req.min_sports_confidence is not None else float(current_user.get("min_sports_confidence", 70.0)),
        req.min_sports_edge if req.min_sports_edge is not None else float(current_user.get("min_sports_edge", 3.0)),
        req.sports_max_wager if req.sports_max_wager is not None else float(current_user.get("sports_max_wager", 10.0)),
        req.sports_include_live if req.sports_include_live is not None else bool(current_user.get("sports_include_live", 0))
    )'''
if old_func in content:
    content = content.replace(old_func, new_func)
else:
    print("Could not find func definition")

with open('backend/auth/routes.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated routes.py")
