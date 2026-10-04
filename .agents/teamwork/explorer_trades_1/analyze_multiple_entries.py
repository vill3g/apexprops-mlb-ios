import os
import sys
import sqlite3
import json
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')
PROJECT_ROOT = r"C:\Users\Vill3\Desktop\ShadowTraderAi"

conn = sqlite3.connect(f"file:{os.path.join(PROJECT_ROOT, 'backend', 'data', 'users.db')}?mode=ro", uri=True)
cur = conn.cursor()

# Query trades with raw_json to parse full flags
cur.execute("SELECT id, user_id, ticker, side, entry_price, exit_price, count, pnl, exit_reason, trading_style, timestamp, raw_json FROM trades;")
rows = cur.fetchall()

print("=== MULTIPLE ENTRY & SCALING ANALYSIS (users.db) ===")

entry_levels = defaultdict(list)
# Classify each trade: Entry 1 (Initial), Entry 2 (Second Entry), Entry 3 (Third Entry)
for r in rows:
    pnl = float(r[7]) if r[7] is not None else None
    if pnl is None:
        continue
    
    style = str(r[9] or "").upper()
    rj_str = r[11]
    is_sec = False
    is_third = False
    reentry_idx = 1
    
    if rj_str:
        try:
            rj = json.loads(rj_str)
            if rj.get("is_third_entry") or rj.get("reentry_index") == 3 or "THIRD" in str(rj.get("trading_style", "")).upper():
                is_third = True
                reentry_idx = 3
            elif rj.get("is_second_entry") or rj.get("reentry_index") == 2 or "SECOND" in str(rj.get("trading_style", "")).upper():
                is_sec = True
                reentry_idx = 2
        except Exception:
            pass
            
    if not is_sec and not is_third:
        if "THIRD" in style:
            is_third = True
            reentry_idx = 3
        elif "SECOND" in style:
            is_sec = True
            reentry_idx = 2

    trade_info = {
        "id": r[0],
        "user_id": r[1],
        "ticker": r[2],
        "side": r[3],
        "entry_price": float(r[4] or 0),
        "exit_price": float(r[5] or 0),
        "count": float(r[6] or 0),
        "pnl": pnl,
        "exit_reason": r[8],
        "timestamp": r[10]
    }
    
    entry_levels[reentry_idx].append(trade_info)

for idx in [1, 2, 3]:
    trades = entry_levels[idx]
    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0.0001]
    losses = [p for p in pnls if p < -0.0001]
    total = len(pnls)
    win_rate = (len(wins) / total * 100) if total else 0.0
    net_pnl = sum(pnls)
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else 0.0
    avg_win = (gross_win / len(wins)) if wins else 0.0
    avg_loss = (sum(losses) / len(losses)) if losses else 0.0
    avg_trade = net_pnl / total if total else 0.0
    avg_count = sum(t["count"] for t in trades) / total if total else 0.0
    
    level_name = "Entry 1 (Initial / Base)" if idx == 1 else (f"Entry 2 (Second Scale)" if idx == 2 else "Entry 3 (Third Scale)")
    print(f"\n--- {level_name} ---")
    print(f"  Count:               {total} trades ({total/len(rows)*100:.1f}% of all trades)")
    print(f"  Wins / Losses:       {len(wins)} / {len(losses)} (Win Rate: {win_rate:.2f}%)")
    print(f"  Net PnL:             ${net_pnl:,.2f}")
    print(f"  Gross Win / Loss:    ${gross_win:,.2f} / ${gross_loss:,.2f}")
    print(f"  Profit Factor:       {pf:.2f}")
    print(f"  Average Win:         ${avg_win:.2f}")
    print(f"  Average Loss:        ${avg_loss:.2f}")
    print(f"  Avg PnL / Trade:     ${avg_trade:.2f}")
    print(f"  Avg Contract Count:  {avg_count:.1f} contracts")

# Now let's group by (user_id, ticker) sequence to see how sequences perform!
# Specifically, when a sequence has Entry 1, how often does it have Entry 2 and Entry 3?
# And what is the sequence total PnL?
print("\n" + "="*75)
print("SEQUENCE-LEVEL PERFORMANCE (Single vs Scaled Multi-Entry Sequences)")
print("="*75)

# Group trades by (user_id, ticker)
sequences = defaultdict(list)
for r in rows:
    pnl = float(r[7]) if r[7] is not None else None
    if pnl is None:
        continue
    uid = r[1]
    ticker = r[2]
    sequences[(uid, ticker)].append({
        "id": r[0],
        "pnl": pnl,
        "style": r[9],
        "ts": r[10],
        "count": float(r[6] or 0),
        "exit_reason": r[8]
    })

seq_by_len = defaultdict(list)
for key, s_trades in sequences.items():
    s_len = len(s_trades)
    tot_pnl = sum(t["pnl"] for t in s_trades)
    seq_by_len[s_len].append({
        "key": key,
        "total_pnl": tot_pnl,
        "trades": s_trades
    })

print(f"{'Seq Length':<12} | {'Num Sequences':<14} | {'Total Trades':<13} | {'Win% (Seq)':<11} | {'Total PnL':<12} | {'Avg PnL/Seq':<12}")
print("-" * 80)
for slen in sorted(seq_by_len.keys()):
    seqs = seq_by_len[slen]
    n_seq = len(seqs)
    tot_pnl = sum(s["total_pnl"] for s in seqs)
    wins = sum(1 for s in seqs if s["total_pnl"] > 0.0001)
    wr = (wins / n_seq * 100) if n_seq else 0
    avg_p = tot_pnl / n_seq if n_seq else 0
    print(f"{slen:<12} | {n_seq:<14} | {slen*n_seq:<13} | {wr:>9.1f}% | ${tot_pnl:>10.2f} | ${avg_p:>10.2f}")

conn.close()
