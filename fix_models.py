import re
with open('backend/database/models.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Add to function signature
sig_old = '''    use_kelly_criterion: bool = False
):'''
sig_new = '''    use_kelly_criterion: bool = False,
    trading_universe: str = "FINANCIAL",
    min_sports_confidence: float = 70.0
):'''
code = code.replace(sig_old, sig_new)

# Add to SQL query
sql_old = '''            use_kelly_criterion = ?
        WHERE id = ?'''
sql_new = '''            use_kelly_criterion = ?,
            trading_universe = ?,
            min_sports_confidence = ?
        WHERE id = ?'''
code = code.replace(sql_old, sql_new)

# Add to SQL parameters
param_old = '''            int(use_kelly_criterion),
            user_id
        )'''
param_new = '''            int(use_kelly_criterion),
            trading_universe,
            min_sports_confidence,
            user_id
        )'''
code = code.replace(param_old, param_new)

with open('backend/database/models.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Updated update_user_config')
