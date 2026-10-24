"""Read-only: settled PAPER results grouped by strategy. Usage: python -I strategy_record.py <db> [<db> ...]"""
import json
import sqlite3
import sys
from collections import defaultdict

groups = defaultdict(lambda: {"n": 0, "wins": 0, "pnl": 0.0})
keys_seen = defaultdict(int)
for path in sys.argv[1:]:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT raw_json FROM trades").fetchall()
    except sqlite3.Error as e:
        print(path, e)
        continue
    for (raw,) in rows:
        try:
            t = json.loads(raw)
        except (TypeError, ValueError):
            continue
        for k in ("trading_style", "strategy", "signal_source", "model_choice", "engine_style"):
            if t.get(k):
                keys_seen[k] += 1
        if str(t.get("mode", "")).upper() != "PAPER" or str(t.get("status", "")).upper() not in ("SETTLED", "CLOSED"):
            continue
        style = t.get("trading_style") or t.get("strategy") or "UNTAGGED"
        g = groups[style]
        g["n"] += 1
        g["pnl"] += float(t.get("pnl") or 0.0)
        g["wins"] += 1 if float(t.get("pnl") or 0.0) > 0 else 0

print("fields present (count):", dict(keys_seen))
print(f"{'strategy':<22}{'trades':>8}{'win %':>8}{'net pnl':>12}")
for style, g in sorted(groups.items(), key=lambda kv: -kv[1]["n"]):
    wr = 100.0 * g["wins"] / g["n"] if g["n"] else 0.0
    print(f"{style:<22}{g['n']:>8}{wr:>7.1f}%{g['pnl']:>12.2f}")
