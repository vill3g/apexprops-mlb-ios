import sqlite3
import json
from datetime import datetime

conn = sqlite3.connect('backend/data/trades.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Use created_at (epoch) for sorting
cursor.execute("SELECT * FROM trades WHERE mode = 'LIVE' ORDER BY created_at DESC")
trades = cursor.fetchall()

print(f"Total LIVE trades found: {len(trades)}")
for i, t in enumerate(trades[:40]):
    print(f"Trade {i}: created_at={t['created_at']}, timestamp={t['timestamp']}, pnl={t['pnl']}, realized_pnl={t['realized_pnl']}, exit_reason={t['exit_reason']}")
    raw_json = json.loads(t['raw_json']) if t['raw_json'] else {}
    source = raw_json.get('trade_source', 'UNKNOWN')
    print(f"  Source: {source}")
