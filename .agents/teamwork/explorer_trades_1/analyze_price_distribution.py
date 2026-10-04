import os
import sys
import sqlite3
import json
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')
PROJECT_ROOT = r"C:\Users\Vill3\Desktop\ShadowTraderAi"

conn = sqlite3.connect(f"file:{os.path.join(PROJECT_ROOT, 'backend', 'data', 'users.db')}?mode=ro", uri=True)
cur = conn.cursor()

cur.execute("SELECT id, entry_price, exit_price, pnl, exit_reason, count FROM trades WHERE pnl IS NOT NULL;")
rows = cur.fetchall()

price_buckets = defaultdict(lambda: {"count": 0, "wins": 0, "losses": 0, "total_pnl": 0.0, "total_cost": 0.0})

for r in rows:
    entry = float(r[1] or 0.5)
    exit_p = float(r[2] or 0.0)
    pnl = float(r[3])
    reason = r[4] or ""
    cnt = float(r[5] or 1.0)
    
    if entry < 0.20:
        bucket = "1. < $0.20 (Deep OTM)"
    elif entry < 0.35:
        bucket = "2. $0.20 - $0.34 (OTM)"
    elif entry < 0.50:
        bucket = "3. $0.35 - $0.49 (Slight OTM)"
    elif entry < 0.65:
        bucket = "4. $0.50 - $0.64 (ATM / Slight ITM)"
    elif entry < 0.80:
        bucket = "5. $0.65 - $0.79 (ITM)"
    else:
        bucket = "6. >= $0.80 (Deep ITM)"
        
    price_buckets[bucket]["count"] += 1
    price_buckets[bucket]["total_pnl"] += pnl
    price_buckets[bucket]["total_cost"] += (entry * cnt)
    if pnl > 0.0001:
        price_buckets[bucket]["wins"] += 1
    elif pnl < -0.0001:
        price_buckets[bucket]["losses"] += 1

print("=== ENTRY CONTRACT PRICE DISTRIBUTION ANALYSIS ===")
print(f"{'Entry Price Range':<32} | {'Trades':<7} | {'Win%':<7} | {'Total PnL':<11} | {'Avg PnL':<9} | {'ProfitFac':<10}")
print("-" * 85)

for b in sorted(price_buckets.keys()):
    s = price_buckets[b]
    cnt = s["count"]
    wr = (s["wins"] / cnt * 100) if cnt else 0.0
    avg_p = s["total_pnl"] / cnt if cnt else 0.0
    # Profit factor
    # need wins / losses sums
    # compute separately
    pass

# Detailed computation for price buckets
bucket_pnls = defaultdict(list)
for r in rows:
    entry = float(r[1] or 0.5)
    pnl = float(r[3])
    if entry < 0.20: b = "1. < $0.20 (Deep OTM)"
    elif entry < 0.35: b = "2. $0.20 - $0.34 (OTM)"
    elif entry < 0.50: b = "3. $0.35 - $0.49 (Slight OTM)"
    elif entry < 0.65: b = "4. $0.50 - $0.64 (ATM / Slight ITM)"
    elif entry < 0.80: b = "5. $0.65 - $0.79 (ITM)"
    else: b = "6. >= $0.80 (Deep ITM)"
    bucket_pnls[b].append(pnl)

for b in sorted(bucket_pnls.keys()):
    pnls = bucket_pnls[b]
    wins = [p for p in pnls if p > 0.0001]
    losses = [p for p in pnls if p < -0.0001]
    tot = len(pnls)
    wr = (len(wins) / tot * 100) if tot else 0.0
    net = sum(pnls)
    gw = sum(wins)
    gl = abs(sum(losses))
    pf = (gw / gl) if gl > 0 else 0.0
    avg_p = net / tot if tot else 0.0
    print(f"{b:<32} | {tot:<7} | {wr:>5.1f}% | ${net:>9.2f} | ${avg_p:>7.2f} | {pf:>10.2f}")

conn.close()
