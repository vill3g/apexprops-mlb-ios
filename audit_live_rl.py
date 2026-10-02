
import sqlite3
from datetime import datetime
conn = sqlite3.connect("backend/data/users.db")
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute("SELECT * FROM trades WHERE user_id = 7 AND signal_source = \"RL_DQN\" AND mode = \"LIVE\"")
rows = c.fetchall()

def get_ts(r):
    try: return datetime.strptime(r["timestamp"].replace(" ET", ""), "%Y-%m-%d %I:%M:%S %p")
    except: return datetime.min

sorted_rows = sorted(rows, key=get_ts)
total_pnl = 0
for r in sorted_rows:
    pnl = r["pnl"] or 0
    total_pnl += pnl
    print("{} | {} | {} | PNL: ${:.2f} | Reason: {} | Entry: {} | Exit: {} | Count: {}".format(
        r["timestamp"], r["ticker"], r["side"], pnl, r["reason"], r["entry_price"], r["exit_price"], r["count"]
    ))
print("Total PNL: ${:.2f}".format(total_pnl))

