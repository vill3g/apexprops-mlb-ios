import os
import sys
import sqlite3
import json
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')
PROJECT_ROOT = r"C:\Users\Vill3\Desktop\ShadowTraderAi"

# Load market_results.json
mr_path = os.path.join(PROJECT_ROOT, "backend", "data", "market_results.json")
with open(mr_path, "r", encoding="utf-8") as f:
    market_results = json.load(f)

print(f"Loaded {len(market_results)} official market results from market_results.json.")

# --- 1. Analyze users.db STOP_LOSS trades ---
conn = sqlite3.connect(f"file:{os.path.join(PROJECT_ROOT, 'backend', 'data', 'users.db')}?mode=ro", uri=True)
cur = conn.cursor()

cur.execute("""
    SELECT id, user_id, ticker, side, entry_price, exit_price, count, pnl, exit_reason, trading_style, timestamp 
    FROM trades;
""")
rows = cur.fetchall()

print("\n" + "="*80)
print("COUNTERFACTUAL EXPIRATION ANALYSIS: WHAT IF STOPPED-OUT TRADES WERE HELD TO EXPIRY?")
print("="*80)

# Categorize trades
stop_loss_trades = []
take_profit_trades = []
settled_trades = []
manual_trades = []

matched_stops = 0
unmatched_stops = 0

for r in rows:
    pnl = float(r[7]) if r[7] is not None else None
    if pnl is None:
        continue
    ticker = r[2]
    side = str(r[3] or "").upper().strip()
    entry = float(r[4] or 0.5)
    exit_p = float(r[5] or 0.0)
    cnt = float(r[6] or 1.0)
    reason = r[8] or ""
    
    # Official result
    official = market_results.get(ticker)
    
    t_obj = {
        "id": r[0],
        "user_id": r[1],
        "ticker": ticker,
        "side": side,
        "entry_price": entry,
        "exit_price": exit_p,
        "count": cnt,
        "actual_pnl": pnl,
        "exit_reason": reason,
        "official_result": official,
        "timestamp": r[10]
    }
    
    cat = reason.split("(")[0].strip() if "(" in reason else reason.split(":")[0].strip()
    if cat == "STOP_LOSS":
        stop_loss_trades.append(t_obj)
    elif cat == "TAKE_PROFIT":
        take_profit_trades.append(t_obj)
    elif cat == "SETTLEMENT":
        settled_trades.append(t_obj)
    elif cat == "MANUAL_CLOSE":
        manual_trades.append(t_obj)

print(f"Total STOP_LOSS trades in users.db: {len(stop_loss_trades)}")
print(f"Total TAKE_PROFIT trades in users.db: {len(take_profit_trades)}")
print(f"Total SETTLEMENT trades in users.db: {len(settled_trades)}")

# Analyze STOP_LOSS counterfactuals
sl_matched = [t for t in stop_loss_trades if t["official_result"] is not None]
print(f"STOP_LOSS trades with known official result: {len(sl_matched)} ({len(sl_matched)/len(stop_loss_trades)*100:.1f}%)")

sl_would_win = []
sl_would_lose = []

for t in sl_matched:
    if t["side"] == t["official_result"]:
        # Contract settled in favor of the trade!
        # Counterfactual PnL: held to $1.00 payout
        # Gross payout: ($1.00 - entry_price) * count
        # In reality, Kalshi fee is taker fee: kalshi_order_fee(entry) + settlement fee
        cf_pnl = (1.0 - t["entry_price"]) * t["count"]
        t["cf_pnl"] = cf_pnl
        sl_would_win.append(t)
    else:
        # Contract settled at $0.00
        # Loss: -entry_price * count
        cf_pnl = -t["entry_price"] * t["count"]
        t["cf_pnl"] = cf_pnl
        sl_would_lose.append(t)

n_matched = len(sl_matched)
n_won = len(sl_would_win)
n_lost = len(sl_would_lose)
win_pct = (n_won / n_matched * 100) if n_matched else 0.0

actual_pnl_matched = sum(t["actual_pnl"] for t in sl_matched)
cf_pnl_matched = sum(t["cf_pnl"] for t in sl_matched)
cf_won_pnl = sum(t["cf_pnl"] for t in sl_would_win)
cf_lost_pnl = sum(t["cf_pnl"] for t in sl_would_lose)

print(f"\n--- STOP_LOSS COUNTERFACTUAL RESULTS ---")
print(f"  Matched Stopped-Out Trades:      {n_matched}")
print(f"  Would Have WON at Settlement:    {n_won} ({win_pct:.1f}%)")
print(f"  Would Have LOST at Settlement:   {n_lost} ({100 - win_pct:.1f}%)")
print(f"  Actual Realized PnL (Stopped Out): ${actual_pnl_matched:,.2f}")
print(f"  Counterfactual PnL (Held to End):  ${cf_pnl_matched:,.2f}")
print(f"  NET DAMAGE OF STOP-LOSS MECHANISM: ${actual_pnl_matched - cf_pnl_matched:,.2f} worse than holding to expiry!")

# Breakdown by trade side
print(f"\nBreakdown by Side for Stopped-Out Trades:")
for side in ["YES", "NO"]:
    side_matched = [t for t in sl_matched if t["side"] == side]
    side_won = [t for t in side_matched if t["side"] == t["official_result"]]
    side_wr = (len(side_won) / len(side_matched) * 100) if side_matched else 0.0
    act_p = sum(t["actual_pnl"] for t in side_matched)
    cf_p = sum(t.get("cf_pnl", 0) for t in side_matched)
    print(f"  Side {side:<3}: {len(side_matched)} trades | Would Win: {len(side_won)} ({side_wr:.1f}%) | Actual: ${act_p:,.2f} | Counterfactual: ${cf_p:,.2f}")

# Analyze TAKE_PROFIT counterfactuals
tp_matched = [t for t in take_profit_trades if t["official_result"] is not None]
tp_would_win = []
tp_would_lose = []
for t in tp_matched:
    if t["side"] == t["official_result"]:
        cf_pnl = (1.0 - t["entry_price"]) * t["count"]
        t["cf_pnl"] = cf_pnl
        tp_would_win.append(t)
    else:
        cf_pnl = -t["entry_price"] * t["count"]
        t["cf_pnl"] = cf_pnl
        tp_would_lose.append(t)

print(f"\n--- TAKE_PROFIT COUNTERFACTUAL RESULTS ---")
print(f"  Matched Take-Profit Trades:      {len(tp_matched)}")
print(f"  Would Have WON at Settlement:    {len(tp_would_win)} ({len(tp_would_win)/len(tp_matched)*100:.1f}%)")
print(f"  Would Have LOST at Settlement:   {len(tp_would_lose)} ({len(tp_would_lose)/len(tp_matched)*100:.1f}%)")
act_tp_pnl = sum(t["actual_pnl"] for t in tp_matched)
cf_tp_pnl = sum(t["cf_pnl"] for t in tp_matched)
print(f"  Actual Realized PnL (Early TP):  ${act_tp_pnl:,.2f}")
print(f"  Counterfactual PnL (Held to End): ${cf_tp_pnl:,.2f}")

conn.close()

# --- 2. Analyze trades.db CONTRACT_STOP_LOSS counterfactuals ---
conn_t = sqlite3.connect(f"file:{os.path.join(PROJECT_ROOT, 'backend', 'data', 'trades.db')}?mode=ro", uri=True)
cur_t = conn_t.cursor()
cur_t.execute("SELECT id, ticker, side, entry_price, exit_price, count, pnl, exit_reason FROM trades;")
tdb_rows = cur_t.fetchall()

tdb_stops = []
for r in tdb_rows:
    pnl = float(r[6]) if r[6] is not None else None
    if pnl is None:
        continue
    reason = r[7] or ""
    if "STOP_LOSS" in reason:
        ticker = r[1]
        side = str(r[2] or "").upper().strip()
        entry = float(r[3] or 0.5)
        cnt = float(r[5] or 1.0)
        official = market_results.get(ticker)
        tdb_stops.append({
            "id": r[0],
            "ticker": ticker,
            "side": side,
            "entry": entry,
            "count": cnt,
            "actual_pnl": pnl,
            "exit_reason": reason,
            "official": official
        })

tdb_matched = [t for t in tdb_stops if t["official"] is not None]
tdb_won = [t for t in tdb_matched if t["side"] == t["official"]]
print(f"\n--- TRADES.DB STOP LOSS COUNTERFACTUAL RESULTS ---")
print(f"  Total Stop Loss Trades:          {len(tdb_stops)}")
print(f"  Matched with Official Result:    {len(tdb_matched)}")
print(f"  Would Have WON at Expiration:    {len(tdb_won)} ({len(tdb_won)/len(tdb_matched)*100:.1f}% if matched)")
act_tdb_pnl = sum(t["actual_pnl"] for t in tdb_matched)
cf_tdb_pnl = sum(((1.0 - t["entry"]) * t["count"] if t["side"] == t["official"] else -t["entry"] * t["count"]) for t in tdb_matched)
print(f"  Actual Realized PnL (Stopped):   ${act_tdb_pnl:,.2f}")
print(f"  Counterfactual PnL (Held):       ${cf_tdb_pnl:,.2f}")
print(f"  NET DAMAGE OF STOP LOSS:         ${act_tdb_pnl - cf_tdb_pnl:,.2f}")

conn_t.close()
