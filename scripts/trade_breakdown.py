"""Read-only breakdown of all closed trades by strategy, exit reason and entry price.

Usage: python -I scripts/trade_breakdown.py
"""
import json
import os
import sqlite3
from collections import defaultdict

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "data")

seen = {}
for db in ("users.db", "trades.db"):
    path = os.path.join(DATA, db)
    if not os.path.exists(path):
        continue
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    for (raw,) in con.execute("SELECT raw_json FROM trades"):
        try:
            t = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if str(t.get("status", "")).upper() not in ("CLOSED", "SETTLED"):
            continue
        seen[(t.get("id"), t.get("ticker"), str(t.get("timestamp")))] = t

trades = list(seen.values())


def row(label, items):
    wins = sum(1 for t in items if float(t.get("pnl") or 0) > 0)
    net = sum(float(t.get("pnl") or 0) for t in items)
    rate = 100.0 * wins / len(items) if items else 0.0
    return f"{label:<24} {len(items):>5}  {rate:5.1f}%  {net:>12,.2f}"


print(f"all closed trades: {len(trades)}")
print(f"{'group':<24} {'n':>5}  {'win':>6}  {'net pnl':>12}")

groups = defaultdict(list)
for t in trades:
    groups[str(t.get("trading_style") or "UNTAGGED")].append(t)
print("-- by strategy (top 10 by count)")
for k in sorted(groups, key=lambda k: -len(groups[k]))[:10]:
    print(row(k, groups[k]))

exits = defaultdict(list)
for t in trades:
    exits[str(t.get("exit_reason") or "NONE").split(" ")[0].split("(")[0]].append(t)
print("-- by exit reason (top 10 by count)")
for k in sorted(exits, key=lambda k: -len(exits[k]))[:10]:
    print(row(k, exits[k]))

prices = defaultdict(list)
for t in trades:
    p = float(t.get("entry_price") or 0)
    lo = int(p * 10) * 10
    prices[f"{lo}-{lo + 10}c"].append(t)
print("-- by entry price")
for k in sorted(prices):
    print(row(k, prices[k]))
