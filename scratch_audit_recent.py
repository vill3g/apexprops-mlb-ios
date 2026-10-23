import sqlite3
import json

con = sqlite3.connect('backend/data/users.db')
cur = con.cursor()
cur.execute("""
    SELECT id, user_id, ticker, side, entry_price, count, status, mode, reason, timestamp, raw_json 
    FROM trades 
    WHERE timestamp LIKE '%2026-10-10%' OR timestamp LIKE '%2026-10-09%' OR id LIKE 'sports_auto_%'
    ORDER BY timestamp DESC
""")
rows = cur.fetchall()
print(f"Total October 9-10 trades found: {len(rows)}")
for r in rows:
    tid, uid, ticker, side, price, count, status, mode, reason, ts, raw_json = r
    src = "unknown"
    if raw_json:
        try:
            d = json.loads(raw_json)
            src = d.get("source") or d.get("pick_source") or d.get("model") or "None in json"
        except:
            pass
    print(f"[{ts}] User: {uid} | Mode: {mode} | Ticker: {ticker} | Side: {side} | Count: {count} | Price: {price} | Status: {status}")
    print(f"   Reason: {reason} | Source: {src}")
    print("-" * 60)
con.close()
