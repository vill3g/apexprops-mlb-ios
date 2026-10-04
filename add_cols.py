import re
with open('backend/database/models.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_cols = '''    "xgb_max_depth": "INTEGER DEFAULT 5",
    "trading_universe": "TEXT DEFAULT 'FINANCIAL'",
    "min_sports_confidence": "REAL DEFAULT 70.0",'''

code = code.replace('"xgb_max_depth": "INTEGER DEFAULT 5",', new_cols)

with open('backend/database/models.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Added sports cols to models.py')
