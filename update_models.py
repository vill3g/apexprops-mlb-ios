import re

with open('backend/database/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_req = '''    "min_sports_confidence": "REAL DEFAULT 70.0",'''
new_req = '''    "min_sports_confidence": "REAL DEFAULT 70.0",
    "min_sports_edge": "REAL DEFAULT 3.0",
    "sports_max_wager": "REAL DEFAULT 10.0",
    "sports_include_live": "BOOLEAN DEFAULT 0",'''
if old_req in content:
    content = content.replace(old_req, new_req)

old_args = '''    use_kelly_criterion: bool = False,
    trading_universe: str = "FINANCIAL",
    min_sports_confidence: float = 70.0
):'''
new_args = '''    use_kelly_criterion: bool = False,
    trading_universe: str = "FINANCIAL",
    min_sports_confidence: float = 70.0,
    min_sports_edge: float = 3.0,
    sports_max_wager: float = 10.0,
    sports_include_live: bool = False
):'''
if old_args in content:
    content = content.replace(old_args, new_args)

old_sql = """                use_kelly_criterion = ?
            WHERE id = ?
        ''', ("""
new_sql = """                use_kelly_criterion = ?,
                min_sports_edge = ?, sports_max_wager = ?, sports_include_live = ?
            WHERE id = ?
        ''', ("""
if old_sql in content:
    content = content.replace(old_sql, new_sql)

old_tuple = '''            1 if use_kelly_criterion else 0, user_id
        ))'''
new_tuple = '''            1 if use_kelly_criterion else 0,
            min_sports_edge, sports_max_wager, 1 if sports_include_live else 0, user_id
        ))'''
if old_tuple in content:
    content = content.replace(old_tuple, new_tuple)

old_copy = '''        "min_edge_cents": float(source_user.get("min_edge_cents", 0.0) or 0.0),
        "use_kelly_criterion": int(bool(source_user.get("use_kelly_criterion", 0)))
    }'''
new_copy = '''        "min_edge_cents": float(source_user.get("min_edge_cents", 0.0) or 0.0),
        "use_kelly_criterion": int(bool(source_user.get("use_kelly_criterion", 0))),
        "min_sports_confidence": float(source_user.get("min_sports_confidence", 70.0)),
        "min_sports_edge": float(source_user.get("min_sports_edge", 3.0)),
        "sports_max_wager": float(source_user.get("sports_max_wager", 10.0)),
        "sports_include_live": int(bool(source_user.get("sports_include_live", 0)))
    }'''
if old_copy in content:
    content = content.replace(old_copy, new_copy)

with open('backend/database/models.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated models.py")
