import json
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

with open('backend/data/trades_history.json', 'r') as f:
    trades = json.load(f)

live = [t for t in trades if t.get('mode','').upper() == 'LIVE'
        and t.get('result') in ('WIN','LOSS')
        and t.get('status') in ('SETTLED','CLOSED')]

print(f"Total settled LIVE trades: {len(live)}")
print()

# --- Overall ---
wins = [t for t in live if t.get('result') == 'WIN']
losses = [t for t in live if t.get('result') == 'LOSS']
total_pnl = sum(float(t.get('pnl',0)) for t in live)
avg_win = sum(float(t.get('pnl',0)) for t in wins) / max(1,len(wins))
avg_loss = sum(float(t.get('pnl',0)) for t in losses) / max(1,len(losses))
rr = avg_win / abs(avg_loss) if avg_loss != 0 else 0
print("=== OVERALL ===")
print(f"  Wins: {len(wins)}  Losses: {len(losses)}  WR: {round(len(wins)/max(1,len(live))*100,1)}%")
print("  Total PNL: $" + str(round(total_pnl,2)))
print("  Avg Win: $" + str(round(avg_win,2)) + "   Avg Loss: $" + str(round(avg_loss,2)) + "   R:R " + str(round(rr,2)))
print()

# --- By Grade ---
print("=== BY CONVICTION GRADE ===")
grades = defaultdict(list)
for t in live:
    grades[t.get('conviction_grade','Unknown')].append(t)
for g, ts in sorted(grades.items()):
    w = sum(1 for t in ts if t.get('result')=='WIN')
    pnl = sum(float(t.get('pnl',0)) for t in ts)
    print(f"  {g:<30} {w}/{len(ts)} = {round(w/len(ts)*100,1)}%  PNL=${round(pnl,2)}")
print()

# --- By Direction ---
print("=== BY DIRECTION ===")
dirs = defaultdict(list)
for t in live:
    dirs[t.get('direction','?')].append(t)
for d, ts in sorted(dirs.items()):
    w = sum(1 for t in ts if t.get('result')=='WIN')
    pnl = sum(float(t.get('pnl',0)) for t in ts)
    print(f"  {d:<10} {w}/{len(ts)} = {round(w/len(ts)*100,1)}%  PNL=${round(pnl,2)}")
print()

# --- By Source ---
print("=== BY TRADE SOURCE ===")
srcs = defaultdict(list)
for t in live:
    srcs[t.get('trade_source','Unknown')].append(t)
for s, ts in sorted(srcs.items()):
    w = sum(1 for t in ts if t.get('result')=='WIN')
    pnl = sum(float(t.get('pnl',0)) for t in ts)
    print(f"  {s:<25} {w}/{len(ts)} = {round(w/len(ts)*100,1)}%  PNL=${round(pnl,2)}")
print()

# --- By Hour of Day (ET) ---
print("=== BY HOUR (ET) ===")
hours = defaultdict(list)
for t in live:
    try:
        dt = datetime.strptime(t.get('timestamp',''), "%Y-%m-%d %I:%M:%S %p ET")
        hours[dt.hour].append(t)
    except: pass
for h in sorted(hours.keys()):
    ts = hours[h]
    w = sum(1 for t in ts if t.get('result')=='WIN')
    pnl = sum(float(t.get('pnl',0)) for t in ts)
    bar = '#' * w + '.' * (len(ts)-w)
    print(f"  {h:02d}:00  {w}/{len(ts)} = {round(w/len(ts)*100,1)}%  PNL=${round(pnl,2)}  [{bar}]")
print()

# --- ML vs Technical agreement ---
print("=== ML vs TECHNICAL SIGNAL AGREEMENT ===")
agree = [t for t in live if 'Model Conflict' not in str(t.get('catalysts',''))]
conflict = [t for t in live if 'Model Conflict' in str(t.get('catalysts',''))]
if agree:
    aw = sum(1 for t in agree if t.get('result')=='WIN')
    print(f"  ML + Tech AGREE  : {aw}/{len(agree)} = {round(aw/len(agree)*100,1)}%  PNL=${round(sum(float(t.get('pnl',0)) for t in agree), 2)}")
if conflict:
    cw = sum(1 for t in conflict if t.get('result')=='WIN')
    print(f"  ML vs Tech CONFLICT: {cw}/{len(conflict)} = {round(cw/len(conflict)*100,1)}%  PNL=${round(sum(float(t.get('pnl',0)) for t in conflict), 2)}")
print()

# --- Biggest wins and losses ---
print("=== TOP 5 WINS ===")
for t in sorted(live, key=lambda x: float(x.get('pnl',0)), reverse=True)[:5]:
    print(f"  ${round(float(t.get('pnl',0)),2)}  {t.get('conviction_grade')}  {t.get('direction')}  {t.get('timestamp','')[:16]}")
print()
print("=== TOP 5 LOSSES ===")
for t in sorted(live, key=lambda x: float(x.get('pnl',0)))[:5]:
    print(f"  ${round(float(t.get('pnl',0)),2)}  {t.get('conviction_grade')}  {t.get('direction')}  {t.get('timestamp','')[:16]}")
