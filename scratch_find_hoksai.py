import sqlite3
import json

for db in ['backend/data/users.db', 'backend/data/trades.db']:
    con = sqlite3.connect(db)
    cur = con.cursor()
    cur.execute("""
        SELECT * FROM trades 
        WHERE ticker LIKE '%HOKSAI%' OR ticker LIKE '%KXNPB%'
    """)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    print(f"=== {db}: Found {len(rows)} NPB trades ===")
    for r in rows:
        row_dict = dict(zip(cols, r))
        print(row_dict.get('timestamp'), "| User:", row_dict.get('user_id'), "| Mode:", row_dict.get('mode'), "| Ticker:", row_dict.get('ticker'), "| Side:", row_dict.get('side'), "| Price:", row_dict.get('entry_price'), "| Count:", row_dict.get('count'), "| Reason:", row_dict.get('reason'))
    con.close()
