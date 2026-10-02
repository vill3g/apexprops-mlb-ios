import sqlite3
import json

conn = sqlite3.connect('backend/data/trades.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get the PM session trades
cursor.execute("SELECT * FROM trades WHERE mode = 'LIVE' ORDER BY created_at DESC LIMIT 15 OFFSET 2")
trades = cursor.fetchall()

print("PM Session Trades ML Metrics:")
for t in reversed(trades[:13]):  # To go chronologically
    raw_json = json.loads(t['raw_json']) if t['raw_json'] else {}
    source = raw_json.get('trade_source', 'UNKNOWN')
    ml_prob = raw_json.get('ml_prob', 'N/A')
    pred_prob = raw_json.get('predicted_probability', 'N/A')
    print(f"Time: {t['timestamp']}, Source: {source}, PnL: {t['pnl']}, ml_prob: {ml_prob}, pred_prob: {pred_prob}")
