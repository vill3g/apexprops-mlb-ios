with open('backend/database/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

replacement = """    "sports_trade_size": "REAL DEFAULT 20.0",
    "sports_sport_config": "TEXT","""

if 'sports_sport_config' not in content:
    content = content.replace('    "sports_trade_size": "REAL DEFAULT 20.0",', replacement)
    with open('backend/database/models.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Added sports_sport_config to models.py')
else:
    print('Already present')
