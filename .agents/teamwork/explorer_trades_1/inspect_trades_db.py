import os
import sys
import sqlite3
import json

sys.stdout.reconfigure(encoding='utf-8')
PROJECT_ROOT = r"C:\Users\Vill3\Desktop\ShadowTraderAi"

print("=== CHECKING trades.db DETAILS ===")
conn = sqlite3.connect(f"file:{os.path.join(PROJECT_ROOT, 'backend', 'data', 'trades.db')}?mode=ro", uri=True)
cur = conn.cursor()

cur.execute("SELECT exit_reason, result, count(*), sum(pnl), avg(pnl) FROM trades GROUP BY exit_reason, result ORDER BY count(*) DESC;")
for r in cur.fetchall():
    print(f"Exit: {str(r[0]):<30} | Result: {str(r[1]):<12} | Count: {r[2]:<5} | Sum PnL: {r[3]:>10.2f} | Avg PnL: {r[4]:>8.2f}")

cur.execute("SELECT mode, count(*), sum(pnl), avg(pnl) FROM trades GROUP BY mode;")
for r in cur.fetchall():
    print(f"Mode: {r[0]} | Count: {r[1]} | Sum PnL: {r[2]:.2f} | Avg PnL: {r[3]:.2f}")

conn.close()
