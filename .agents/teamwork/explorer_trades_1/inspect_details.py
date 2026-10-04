import os
import sys
import sqlite3
import json
import re

sys.stdout.reconfigure(encoding='utf-8')
PROJECT_ROOT = r"C:\Users\Vill3\Desktop\ShadowTraderAi"

conn = sqlite3.connect(f"file:{os.path.join(PROJECT_ROOT, 'backend', 'data', 'users.db')}?mode=ro", uri=True)
cur = conn.cursor()

# Check exit reasons by category
cur.execute("SELECT exit_reason, pnl FROM trades WHERE exit_reason IS NOT NULL;")
rows = cur.fetchall()

categories = {}
for r, pnl in rows:
    pnl = float(pnl) if pnl is not None else 0.0
    prefix = r.split("(")[0].strip() if "(" in r else r.split(":")[0].strip()
    if prefix not in categories:
        categories[prefix] = {"count": 0, "wins": 0, "losses": 0, "total_pnl": 0.0, "pnl_list": []}
    categories[prefix]["count"] += 1
    categories[prefix]["total_pnl"] += pnl
    categories[prefix]["pnl_list"].append(pnl)
    if pnl > 0:
        categories[prefix]["wins"] += 1
    elif pnl < 0:
        categories[prefix]["losses"] += 1

print("=== EXIT REASON CATEGORIES IN users.db ===")
for cat, stats in sorted(categories.items(), key=lambda x: x[1]["count"], reverse=True):
    wr = (stats["wins"] / stats["count"] * 100) if stats["count"] else 0
    avg_pnl = stats["total_pnl"] / stats["count"] if stats["count"] else 0
    print(f"{cat:<25} | Count: {stats['count']:<5} | Wins: {stats['wins']:<5} | Losses: {stats['losses']:<5} | WinRate: {wr:>5.1f}% | Total PnL: {stats['total_pnl']:>8.2f} | Avg PnL: {avg_pnl:>6.2f}")

# Check NULL exit_reason (e.g. settled or open)
cur.execute("SELECT status, count(*), sum(cast(pnl as real)), avg(cast(pnl as real)) FROM trades WHERE exit_reason IS NULL GROUP BY status;")
print("\n--- NULL exit_reason trades by status ---")
for r in cur.fetchall():
    print(r)

# Inspect raw_json contents
cur.execute("SELECT raw_json FROM trades WHERE raw_json IS NOT NULL LIMIT 5;")
for i, (rj,) in enumerate(cur.fetchall()):
    try:
        parsed = json.loads(rj)
        print(f"\n--- raw_json sample {i+1} keys ---: {list(parsed.keys())}")
        if "market_snapshot" in parsed:
            print("  market_snapshot type:", type(parsed["market_snapshot"]))
            print("  market_snapshot:", str(parsed["market_snapshot"])[:200])
        if "catalysts" in parsed:
            print("  catalysts:", str(parsed["catalysts"])[:200])
    except Exception as e:
        print(f"Error parsing raw_json: {e}")

conn.close()
