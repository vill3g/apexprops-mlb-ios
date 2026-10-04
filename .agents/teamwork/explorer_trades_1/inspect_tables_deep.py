import os
import sys
import sqlite3
import json

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = r"C:\Users\Vill3\Desktop\ShadowTraderAi"

print("=== INSPECTING trades.db ===")
db_path = os.path.join(PROJECT_ROOT, "backend", "data", "trades.db")
conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
cur = conn.cursor()
cur.execute("PRAGMA table_info(trades);")
cols = [c[1] for c in cur.fetchall()]
print(f"Columns in trades.db trades: {cols}")
cur.execute("SELECT id, asset, ticker, timestamp, side, entry_price, exit_price, count, cost, mode, status, result, pnl, exit_reason FROM trades LIMIT 3;")
rows = cur.fetchall()
print(f"Sample 3 rows from trades.db:")
for r in rows:
    print(r)
conn.close()

print("\n=== INSPECTING users.db trades table ===")
db_path = os.path.join(PROJECT_ROOT, "backend", "data", "users.db")
conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
cur = conn.cursor()
cur.execute("PRAGMA table_info(trades);")
cols2 = [c[1] for c in cur.fetchall()]
print(f"Columns in users.db trades: {cols2}")
cur.execute("SELECT * FROM trades LIMIT 2;")
rows = cur.fetchall()
for r in rows:
    # Print as dict of col: val excluding long strings
    row_dict = {cols2[i]: (str(r[i])[:60] if r[i] is not None else None) for i in range(len(cols2))}
    print(row_dict)

print("\n=== INSPECTING users.db order_intents table ===")
cur.execute("PRAGMA table_info(order_intents);")
cols_oi = [c[1] for c in cur.fetchall()]
print(f"Columns in users.db order_intents: {cols_oi}")
cur.execute("SELECT * FROM order_intents LIMIT 2;")
rows = cur.fetchall()
for r in rows:
    row_dict = {cols_oi[i]: (str(r[i])[:60] if r[i] is not None else None) for i in range(len(cols_oi))}
    print(row_dict)
conn.close()

print("\n=== INSPECTING backend/data/trades_history.json ===")
th_path = os.path.join(PROJECT_ROOT, "backend", "data", "trades_history.json")
if os.path.exists(th_path):
    with open(th_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        print(f"trades_history.json: count = {len(data) if isinstance(data, list) else type(data)}")
        if isinstance(data, list) and len(data) > 0:
            print("Keys:", list(data[0].keys()))
            # summarize first item
            print({k: (str(v)[:60] if v is not None else None) for k, v in data[0].items()})

print("\n=== INSPECTING backend/data/rl_shadow_trades.json ===")
rl_path = os.path.join(PROJECT_ROOT, "backend", "data", "rl_shadow_trades.json")
if os.path.exists(rl_path):
    with open(rl_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        print(f"rl_shadow_trades.json: count = {len(data) if isinstance(data, list) else type(data)}")
        if isinstance(data, list) and len(data) > 0:
            print("Keys:", list(data[0].keys()))
            print({k: (str(v)[:60] if v is not None else None) for k, v in data[0].items()})
