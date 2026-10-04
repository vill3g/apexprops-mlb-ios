import os
import sys
import sqlite3
import json
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')
PROJECT_ROOT = r"C:\Users\Vill3\Desktop\ShadowTraderAi"

conn = sqlite3.connect(f"file:{os.path.join(PROJECT_ROOT, 'backend', 'data', 'users.db')}?mode=ro", uri=True)
cur = conn.cursor()

cur.execute("""
    SELECT id, user_id, ticker, side, entry_price, exit_price, count, pnl, exit_reason, trading_style, timestamp, raw_json 
    FROM trades 
    ORDER BY user_id, ticker, timestamp ASC;
""")
rows = cur.fetchall()

sequences = defaultdict(list)
for r in rows:
    pnl = float(r[7]) if r[7] is not None else None
    if pnl is None:
        continue
    uid = r[1]
    ticker = r[2]
    
    style = str(r[9] or "").upper()
    rj_str = r[11]
    is_sec = False
    is_third = False
    reentry_idx = 1
    market_snapshot = {}
    catalysts = []
    
    if rj_str:
        try:
            rj = json.loads(rj_str)
            if rj.get("is_third_entry") or rj.get("reentry_index") == 3 or "THIRD" in str(rj.get("trading_style", "")).upper():
                is_third = True
                reentry_idx = 3
            elif rj.get("is_second_entry") or rj.get("reentry_index") == 2 or "SECOND" in str(rj.get("trading_style", "")).upper():
                is_sec = True
                reentry_idx = 2
            market_snapshot = rj.get("market_snapshot") or {}
            catalysts = rj.get("catalysts") or []
        except Exception:
            pass
            
    if not is_sec and not is_third:
        if "THIRD" in style:
            is_third = True
            reentry_idx = 3
        elif "SECOND" in style:
            is_sec = True
            reentry_idx = 2

    sequences[(uid, ticker)].append({
        "id": r[0],
        "user_id": uid,
        "ticker": ticker,
        "side": r[3],
        "entry_price": float(r[4] or 0),
        "exit_price": float(r[5] or 0),
        "count": float(r[6] or 0),
        "pnl": pnl,
        "exit_reason": r[8] or "",
        "style": r[9],
        "timestamp": r[10],
        "reentry_idx": reentry_idx,
        "market_snapshot": market_snapshot,
        "catalysts": catalysts
    })

print("=== TRANSITION ANALYSIS IN SEQUENCES ===")
# For sequences of length >= 2, analyze:
# Condition A: Trade 1 was a STOP_LOSS -> Trade 2 outcome
# Condition B: Trade 1 was a TAKE_PROFIT -> Trade 2 outcome
# Condition C: Trade 1 was a SETTLEMENT WIN -> Trade 2 outcome

transitions = defaultdict(lambda: {"count": 0, "wins": 0, "losses": 0, "total_pnl": 0.0, "trades": []})

for key, s_trades in sequences.items():
    if len(s_trades) < 2:
        continue
    t1 = s_trades[0]
    t2 = s_trades[1]
    
    t1_exit = t1["exit_reason"]
    t1_cat = t1_exit.split("(")[0].strip() if "(" in t1_exit else t1_exit.split(":")[0].strip()
    if not t1_cat:
        t1_cat = "WIN" if t1["pnl"] > 0 else "LOSS"
    
    t1_outcome = "T1_WIN" if t1["pnl"] > 0 else ("T1_LOSS" if t1["pnl"] < 0 else "T1_FLAT")
    cond = f"{t1_outcome} ({t1_cat})"
    
    transitions[cond]["count"] += 1
    transitions[cond]["total_pnl"] += t2["pnl"]
    transitions[cond]["trades"].append(t2)
    if t2["pnl"] > 0.0001:
        transitions[cond]["wins"] += 1
    elif t2["pnl"] < -0.0001:
        transitions[cond]["losses"] += 1

print(f"{'Condition (Trade 1 Exit)':<35} | {'Count':<6} | {'T2 Win%':<9} | {'T2 Total PnL':<14} | {'T2 Avg PnL':<11} | {'Combined PnL':<13}")
print("-" * 95)
for cond, stats in sorted(transitions.items(), key=lambda x: x[1]["count"], reverse=True):
    cnt = stats["count"]
    wr = (stats["wins"] / cnt * 100) if cnt else 0.0
    avg_pnl = stats["total_pnl"] / cnt if cnt else 0.0
    # Combined PnL of T1 + T2 for these sequences
    # find matching sequences
    comb_pnl = 0.0
    for key, s_trades in sequences.items():
        if len(s_trades) >= 2:
            t1 = s_trades[0]
            t2 = s_trades[1]
            t1_exit = t1["exit_reason"]
            t1_cat = t1_exit.split("(")[0].strip() if "(" in t1_exit else t1_exit.split(":")[0].strip()
            if not t1_cat: t1_cat = "WIN" if t1["pnl"] > 0 else "LOSS"
            t1_outcome = "T1_WIN" if t1["pnl"] > 0 else ("T1_LOSS" if t1["pnl"] < 0 else "T1_FLAT")
            if f"{t1_outcome} ({t1_cat})" == cond:
                comb_pnl += (t1["pnl"] + t2["pnl"])
    print(f"{cond:<35} | {cnt:<6} | {wr:>7.1f}% | ${stats['total_pnl']:>12.2f} | ${avg_pnl:>9.2f} | ${comb_pnl:>11.2f}")

conn.close()
