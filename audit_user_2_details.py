import sqlite3
import json

conn = sqlite3.connect('backend/data/users.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("SELECT * FROM trades WHERE user_id=2 ORDER BY id DESC LIMIT 20")
rows = [dict(r) for r in c.fetchall()]

for r in rows:
    raw = {}
    try:
        raw = json.loads(r.get('raw_json') or '{}')
    except:
        pass
    print("=" * 80)
    print(f"ID: {r['id']}")
    print(f"Timestamp: {r['timestamp']} | Settled: {r.get('settled_at')}")
    print(f"Ticker: {r['ticker']} | Side: {r['side']} | Mode: {r['mode']} | Status: {r['status']}")
    print(f"Contracts: {r['count']} | Entry: ${r['entry_price']} | Exit: ${r['exit_price']} | PnL: ${r['pnl']}")
    print(f"Style: {r['trading_style']} | Reason: {r['reason']}")
    print(f"Exit Reason: {r['exit_reason']}")
    if raw:
        print(f"Raw Order Details: kalshi_order_id={raw.get('order_id')}, client_id={raw.get('client_order_id')}, fee={raw.get('fee')}")
