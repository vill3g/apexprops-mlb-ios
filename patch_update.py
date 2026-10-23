with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    c = f.read()
target = 'sports_active_props=req.sports_active_props\n    )'
replacement = 'sports_active_props=req.sports_active_props,\n        sports_sport_config=req.sports_sport_config\n    )'
c = c.replace(target, replacement)
with open('backend/auth/routes.py', 'w', encoding='utf-8') as f:
    f.write(c)
print('Patched update call in routes.py')
