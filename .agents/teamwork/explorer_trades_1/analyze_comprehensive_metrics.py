import os
import sys
import sqlite3
import json
import math
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')
PROJECT_ROOT = r"C:\Users\Vill3\Desktop\ShadowTraderAi"

def calculate_metrics(pnl_series):
    if not pnl_series:
        return {}
    total_trades = len(pnl_series)
    wins = [p for p in pnl_series if p > 0.0001]
    losses = [p for p in pnl_series if p < -0.0001]
    flats = [p for p in pnl_series if abs(p) <= 0.0001]
    
    n_wins = len(wins)
    n_losses = len(losses)
    n_flats = len(flats)
    win_rate = (n_wins / total_trades) * 100 if total_trades > 0 else 0.0
    
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    net_pnl = sum(pnl_series)
    
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0.0)
    avg_win = (gross_profit / n_wins) if n_wins > 0 else 0.0
    avg_loss = (sum(losses) / n_losses) if n_losses > 0 else 0.0
    win_loss_ratio = (avg_win / abs(avg_loss)) if avg_loss != 0 else float('inf')
    expectancy = (net_pnl / total_trades) if total_trades > 0 else 0.0
    
    # Calculate Max Drawdown
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnl_series:
        cumulative += p
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd
            
    return {
        "total": total_trades,
        "wins": n_wins,
        "losses": n_losses,
        "flats": n_flats,
        "win_rate": win_rate,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "net_pnl": net_pnl,
        "profit_factor": profit_factor,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "win_loss_ratio": win_loss_ratio,
        "expectancy": expectancy,
        "max_dd": max_dd
    }

def print_metrics_table(title, metrics):
    print(f"\n{'='*75}")
    print(f" {title}")
    print(f"{'='*75}")
    if not metrics:
        print("  No trades.")
        return
    print(f"  Total Trades:        {metrics['total']}")
    print(f"  Wins / Losses / Flat: {metrics['wins']} / {metrics['losses']} / {metrics['flats']}")
    print(f"  Win Rate:            {metrics['win_rate']:.2f}%")
    print(f"  Net P&L:             ${metrics['net_pnl']:,.2f}")
    print(f"  Gross Profit:        ${metrics['gross_profit']:,.2f}")
    print(f"  Gross Loss:          ${metrics['gross_loss']:,.2f}")
    pf_str = f"{metrics['profit_factor']:.2f}" if metrics['profit_factor'] != float('inf') else "Inf"
    print(f"  Profit Factor:       {pf_str}")
    print(f"  Average Win:         ${metrics['avg_win']:.2f}")
    print(f"  Average Loss:        ${metrics['avg_loss']:.2f}")
    wl_str = f"{metrics['win_loss_ratio']:.2f}" if metrics['win_loss_ratio'] != float('inf') else "Inf"
    print(f"  Win/Loss Payoff:     {wl_str}")
    print(f"  Expectancy / Trade:  ${metrics['expectancy']:.2f}")
    print(f"  Max Drawdown:        ${metrics['max_dd']:,.2f}")

# --- 1. Analyze users.db ---
conn_users = sqlite3.connect(f"file:{os.path.join(PROJECT_ROOT, 'backend', 'data', 'users.db')}?mode=ro", uri=True)
cur_u = conn_users.cursor()

cur_u.execute("SELECT id, user_id, mode, status, pnl, exit_reason, trading_style, signal_source, timestamp FROM trades;")
user_trades = cur_u.fetchall()

all_pnls_users = [float(r[4]) for r in user_trades if r[4] is not None]
live_pnls_users = [float(r[4]) for r in user_trades if r[2] == 'LIVE' and r[4] is not None]
paper_pnls_users = [float(r[4]) for r in user_trades if r[2] == 'PAPER' and r[4] is not None]

print_metrics_table("USERS.DB — ALL CLOSED/SETTLED TRADES", calculate_metrics(all_pnls_users))
print_metrics_table("USERS.DB — LIVE TRADES ONLY", calculate_metrics(live_pnls_users))
print_metrics_table("USERS.DB — PAPER TRADES ONLY", calculate_metrics(paper_pnls_users))

# By User
print(f"\n{'-'*75}")
print("USERS.DB — BREAKDOWN BY USER ACCOUNT")
print(f"{'-'*75}")
print(f"{'User':<8} | {'Mode':<6} | {'Trades':<7} | {'Win%':<7} | {'Net PnL':<10} | {'ProfitFac':<10} | {'Avg Win':<8} | {'Avg Loss':<8} | {'Max DD':<8}")
print(f"{'-'*75}")

user_groups = defaultdict(list)
for r in user_trades:
    if r[4] is not None:
        user_groups[(r[1], r[2])].append(float(r[4]))

for (uid, mode), pnls in sorted(user_groups.items(), key=lambda x: str(x[0][0])):
    m = calculate_metrics(pnls)
    pf_str = f"{m['profit_factor']:.2f}" if m['profit_factor'] != float('inf') else "Inf"
    print(f"{str(uid):<8} | {mode:<6} | {m['total']:<7} | {m['win_rate']:>5.1f}% | ${m['net_pnl']:>8.2f} | {pf_str:>10} | ${m['avg_win']:>6.2f} | ${m['avg_loss']:>6.2f} | ${m['max_dd']:>6.2f}")

# By Exit Reason Category in users.db
print(f"\n{'-'*75}")
print("USERS.DB — BREAKDOWN BY EXIT REASON CATEGORY")
print(f"{'-'*75}")
print(f"{'Exit Category':<22} | {'Trades':<7} | {'Win%':<7} | {'Net PnL':<10} | {'Gross Win':<10} | {'Gross Loss':<10} | {'Avg PnL':<8}")
print(f"{'-'*75}")

exit_groups = defaultdict(list)
for r in user_trades:
    if r[4] is not None:
        exit_r = r[5] or "UNSPECIFIED"
        cat = exit_r.split("(")[0].strip() if "(" in exit_r else exit_r.split(":")[0].strip()
        exit_groups[cat].append(float(r[4]))

for cat, pnls in sorted(exit_groups.items(), key=lambda x: len(x[1]), reverse=True):
    m = calculate_metrics(pnls)
    print(f"{cat:<22} | {m['total']:<7} | {m['win_rate']:>5.1f}% | ${m['net_pnl']:>8.2f} | ${m['gross_profit']:>8.2f} | ${m['gross_loss']:>8.2f} | ${m['expectancy']:>6.2f}")

conn_users.close()

# --- 2. Analyze trades.db ---
conn_t = sqlite3.connect(f"file:{os.path.join(PROJECT_ROOT, 'backend', 'data', 'trades.db')}?mode=ro", uri=True)
cur_t = conn_t.cursor()
cur_t.execute("SELECT id, mode, status, result, pnl, exit_reason FROM trades;")
trades_db_rows = cur_t.fetchall()

all_pnls_tdb = [float(r[4]) for r in trades_db_rows if r[4] is not None]
live_pnls_tdb = [float(r[4]) for r in trades_db_rows if r[1] == 'LIVE' and r[4] is not None]
paper_pnls_tdb = [float(r[4]) for r in trades_db_rows if r[1] == 'PAPER' and r[4] is not None]

print_metrics_table("TRADES.DB — ALL TRADES", calculate_metrics(all_pnls_tdb))
print_metrics_table("TRADES.DB — LIVE TRADES", calculate_metrics(live_pnls_tdb))
print_metrics_table("TRADES.DB — PAPER TRADES", calculate_metrics(paper_pnls_tdb))

print(f"\n{'-'*75}")
print("TRADES.DB — BREAKDOWN BY EXIT REASON")
print(f"{'-'*75}")
print(f"{'Exit Reason':<28} | {'Trades':<7} | {'Win%':<7} | {'Net PnL':<12} | {'Avg Win':<8} | {'Avg Loss':<8}")
print(f"{'-'*75}")

tdb_exit_groups = defaultdict(list)
for r in trades_db_rows:
    if r[4] is not None:
        er = r[5] or "NATURAL_SETTLEMENT"
        tdb_exit_groups[er].append(float(r[4]))

for er, pnls in sorted(tdb_exit_groups.items(), key=lambda x: len(x[1]), reverse=True):
    m = calculate_metrics(pnls)
    print(f"{er:<28} | {m['total']:<7} | {m['win_rate']:>5.1f}% | ${m['net_pnl']:>10.2f} | ${m['avg_win']:>6.2f} | ${m['avg_loss']:>6.2f}")

conn_t.close()
