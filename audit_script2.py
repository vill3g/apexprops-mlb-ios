import sqlite3
import json

conn = sqlite3.connect('backend/data/trades.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT * FROM trades WHERE mode = 'LIVE' ORDER BY created_at DESC")
trades = cursor.fetchall()

print(f"Total LIVE trades found: {len(trades)}")
for i, t in enumerate(trades[:100]):
    print(f"Trade {i}: created_at={t['created_at']}, timestamp={t['timestamp']}, pnl={t['pnl']}, realized_pnl={t['realized_pnl']}")
