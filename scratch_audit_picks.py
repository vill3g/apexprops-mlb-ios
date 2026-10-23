import sqlite3
import json
import time
from datetime import datetime

con = sqlite3.connect('backend/data/users.db')
cur = con.cursor()
cur.execute("""
    SELECT id, user_id, ticker, side, entry_price, count, status, mode, reason, ml_reasoning, raw_json, timestamp 
    FROM trades 
    WHERE mode = 'LIVE' 
    ORDER BY id DESC LIMIT 50
""")
rows = cur.fetchall()
print(f"Total LIVE trades found: {len(rows)}")
for r in rows:
    tid, uid, ticker, side, price, count, status, mode, reason, ml_reasoning, raw_json, ts = r
    print(f"[{ts}] User: {uid} | Ticker: {ticker} | Side: {side} | Price: {price} | Count: {count}")
    print(f"   Reason: {reason}")
    if ml_reasoning:
        print(f"   ML Reasoning: {ml_reasoning}")
    if raw_json:
        try:
            d = json.loads(raw_json)
            print(f"   Source: {d.get('source')} | Model: {d.get('model')} | Pick Source: {d.get('pick_source')} | Conf: {d.get('confidence')}")
        except:
            pass
    print("-" * 60)
con.close()
