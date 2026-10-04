import os
import sys
import sqlite3
import json
import glob

sys.stdout.reconfigure(encoding='utf-8')
PROJECT_ROOT = r"C:\Users\Vill3\Desktop\ShadowTraderAi"

conn = sqlite3.connect(f"file:{os.path.join(PROJECT_ROOT, 'backend', 'data', 'users.db')}?mode=ro", uri=True)
cur = conn.cursor()

cur.execute("PRAGMA table_info(users);")
print("Columns in users table:", [c[1] for c in cur.fetchall()])
cur.execute("SELECT * FROM users;")
print("Users in users.db:")
for u in cur.fetchall():
    print(u)

cur.execute("SELECT user_id, count(*), min(timestamp), max(timestamp), sum(cast(pnl as real)) FROM trades GROUP BY user_id;")
print("\nTrades per user in users.db:")
for row in cur.fetchall():
    print(f"User {row[0]}: {row[1]} trades | from {row[2]} to {row[3]} | Total PnL: {row[4]:.2f}")

conn.close()

user_jsons = glob.glob(os.path.join(PROJECT_ROOT, "backend", "data", "users", "*", "trades_history.json"))
print(f"\nUser JSON files found: {len(user_jsons)}")
for uj in user_jsons:
    with open(uj, "r", encoding="utf-8") as f:
        data = json.load(f)
        user_id = os.path.basename(os.path.dirname(uj))
        print(f"User {user_id} JSON trades: {len(data)}")
        if len(data) > 0:
            scaling_keys = [k for k in ['is_second_entry', 'is_third_entry', 'is_profit_reentry', 'reentry_index'] if k in data[0]]
            second_entries = sum(1 for d in data if d.get('is_second_entry'))
            third_entries = sum(1 for d in data if d.get('is_third_entry'))
            print(f"  Scaling keys: {scaling_keys} | second: {second_entries}, third: {third_entries}")
