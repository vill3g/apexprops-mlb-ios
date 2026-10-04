import os
import sys
import sqlite3
import json
import glob
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')
PROJECT_ROOT = r"C:\Users\Vill3\Desktop\ShadowTraderAi"

print("=== CHECKING users.db TRADES BREAKDOWN ===")
conn = sqlite3.connect(f"file:{os.path.join(PROJECT_ROOT, 'backend', 'data', 'users.db')}?mode=ro", uri=True)
cur = conn.cursor()

# Breakdown by user_id
cur.execute("SELECT user_id, mode, status, count(*), sum(cast(pnl as real)) FROM trades GROUP BY user_id, mode, status;")
for row in cur.fetchall():
    print(f"User: {row[0]} | Mode: {row[1]} | Status: {row[2]} | Count: {row[3]} | Total PnL: {row[4]:.2f}")

# Breakdown by exit_reason
print("\n--- Exit Reasons in users.db ---")
cur.execute("SELECT exit_reason, count(*), avg(cast(pnl as real)), sum(cast(pnl as real)) FROM trades GROUP BY exit_reason ORDER BY count(*) DESC;")
for row in cur.fetchall():
    print(f"Exit: {str(row[0]):<35} | Count: {row[1]:<5} | Avg PnL: {row[2]:>8.2f} | Sum PnL: {row[3]:>10.2f}")

# Breakdown by trading_style
print("\n--- Trading Styles in users.db ---")
cur.execute("SELECT trading_style, count(*), avg(cast(pnl as real)), sum(cast(pnl as real)) FROM trades GROUP BY trading_style ORDER BY count(*) DESC;")
for row in cur.fetchall():
    print(f"Style: {str(row[0]):<20} | Count: {row[1]:<5} | Avg PnL: {row[2]:>8.2f} | Sum PnL: {row[3]:>10.2f}")

# Breakdown by signal_source
print("\n--- Signal Sources in users.db ---")
cur.execute("SELECT signal_source, count(*), avg(cast(pnl as real)), sum(cast(pnl as real)) FROM trades GROUP BY signal_source ORDER BY count(*) DESC;")
for row in cur.fetchall():
    print(f"Signal: {str(row[0]):<20} | Count: {row[1]:<5} | Avg PnL: {row[2]:>8.2f} | Sum PnL: {row[3]:>10.2f}")

# Check min/max timestamp
cur.execute("SELECT min(timestamp), max(timestamp) FROM trades;")
min_ts, max_ts = cur.fetchone()
print(f"\nTimestamp range: {min_ts} to {max_ts}")

conn.close()

print("\n=== CHECKING trades.db BREAKDOWN ===")
conn = sqlite3.connect(f"file:{os.path.join(PROJECT_ROOT, 'backend', 'data', 'trades.db')}?mode=ro", uri=True)
cur = conn.cursor()
cur.execute("SELECT mode, status, result, count(*), sum(pnl) FROM trades GROUP BY mode, status, result;")
for row in cur.fetchall():
    print(f"Mode: {row[0]} | Status: {row[1]} | Result: {row[2]} | Count: {row[3]} | PnL: {row[4]}")
cur.execute("SELECT min(timestamp), max(timestamp) FROM trades;")
print(f"Timestamp range: {cur.fetchone()}")
conn.close()
