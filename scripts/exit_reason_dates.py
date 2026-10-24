"""Read-only: when did trades with a given exit reason happen? Usage: python -I scripts/exit_reason_dates.py CONTRACT_STOP_LOSS"""
import json
import os
import sqlite3
import sys
from collections import Counter

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "data")
reason = sys.argv[1] if len(sys.argv) > 1 else "CONTRACT_STOP_LOSS"
days = Counter()
pnl = 0.0
seen = set()
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
        if not str(t.get("exit_reason") or "").upper().startswith(reason):
            continue
        key = (t.get("id"), t.get("ticker"), str(t.get("timestamp")))
        if key in seen:
            continue
        seen.add(key)
        days[str(t.get("timestamp") or "")[:10]] += 1
        pnl += float(t.get("pnl") or 0)
print(f"{reason}: {sum(days.values())} trades, net ${pnl:,.2f}")
for d in sorted(days):
    print(f"  {d or 'unknown'}  {days[d]}")
