import os
import sys
import sqlite3
import json
import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')
PROJECT_ROOT = r"C:\Users\Vill3\Desktop\ShadowTraderAi"

def parse_epoch(ts_str):
    if not ts_str:
        return None
    try:
        if isinstance(ts_str, (int, float)):
            return float(ts_str)
        # Check if float as string
        try:
            return float(ts_str)
        except ValueError:
            pass
        if "ET" in ts_str:
            dt = datetime.datetime.strptime(ts_str.replace(" ET", ""), "%Y-%m-%d %I:%M:%S %p")
            return dt.replace(tzinfo=ZoneInfo("America/New_York")).timestamp()
        if "T" in ts_str:
            # ISO format
            clean_ts = ts_str.split(".")[0]
            if "+" in ts_str or "-" in ts_str[-6:]:
                # Has timezone
                dt = datetime.datetime.fromisoformat(ts_str)
                return dt.timestamp()
            dt = datetime.datetime.fromisoformat(clean_ts)
            return dt.replace(tzinfo=datetime.timezone.utc).timestamp()
    except Exception as e:
        pass
    return None

conn = sqlite3.connect(f"file:{os.path.join(PROJECT_ROOT, 'backend', 'data', 'users.db')}?mode=ro", uri=True)
cur = conn.cursor()

cur.execute("SELECT id, user_id, ticker, side, entry_price, pnl, exit_reason, trading_style, timestamp, raw_json FROM trades;")
rows = cur.fetchall()

print("=== ENTRY TIMING ANALYSIS WITHIN 15-MINUTE CONTRACT (users.db) ===")

timing_buckets = defaultdict(list)
timing_intervals = defaultdict(list) # 0-3m (Early), 3-6m (Mid-Early), 6-9m (Mid), 9-12m (Late), 12-15m (Terminal)

parsed_count = 0
unparsed_count = 0

for r in rows:
    pnl = float(r[5]) if r[5] is not None else None
    if pnl is None:
        continue
    
    ts_str = r[8]
    epoch = parse_epoch(ts_str)
    if epoch is None and r[9]:
        try:
            rj = json.loads(r[9])
            epoch = parse_epoch(rj.get("timestamp"))
        except Exception:
            pass
            
    if epoch is None:
        unparsed_count += 1
        continue
        
    parsed_count += 1
    # Modulo 900 seconds (15 minutes)
    sec_into_candle = int(epoch) % 900
    min_into_candle = sec_into_candle // 60
    sec_left = 900 - sec_into_candle
    
    trade_data = {
        "id": r[0],
        "pnl": pnl,
        "entry_price": float(r[4] or 0),
        "exit_reason": r[6] or "",
        "style": r[7] or "",
        "sec_into_candle": sec_into_candle,
        "min_into_candle": min_into_candle,
        "sec_left": sec_left
    }
    
    timing_buckets[min_into_candle].append(trade_data)
    
    if min_into_candle < 3:
        phase = "01_Open (0-3m)"
    elif min_into_candle < 6:
        phase = "02_Mid_Early (3-6m)"
    elif min_into_candle < 9:
        phase = "03_Mid (6-9m)"
    elif min_into_candle < 12:
        phase = "04_Late (9-12m)"
    else:
        phase = "05_Terminal (12-15m)"
        
    timing_intervals[phase].append(trade_data)

print(f"Successfully parsed timestamp for {parsed_count} trades ({unparsed_count} unparsed).")

print(f"\n{'-'*85}")
print("BREAKDOWN BY EXACT MINUTE OF ENTRY (0 to 14 minutes into 15m candle)")
print(f"{'-'*85}")
print(f"{'Minute':<8} | {'Trades':<7} | {'Win%':<7} | {'Net PnL':<11} | {'Avg PnL':<9} | {'Avg Win':<8} | {'Avg Loss':<9} | {'Stop-Loss%':<10}")
print(f"{'-'*85}")

for m in range(15):
    t_list = timing_buckets[m]
    if not t_list:
        continue
    pnls = [t["pnl"] for t in t_list]
    wins = [p for p in pnls if p > 0.0001]
    losses = [p for p in pnls if p < -0.0001]
    sl_count = sum(1 for t in t_list if "STOP_LOSS" in t["exit_reason"])
    sl_pct = (sl_count / len(t_list) * 100) if t_list else 0.0
    tot = len(pnls)
    wr = (len(wins) / tot * 100) if tot else 0.0
    net = sum(pnls)
    avg_p = net / tot if tot else 0.0
    avg_w = (sum(wins) / len(wins)) if wins else 0.0
    avg_l = (sum(losses) / len(losses)) if losses else 0.0
    print(f"Min {m:>2}    | {tot:<7} | {wr:>5.1f}% | ${net:>9.2f} | ${avg_p:>7.2f} | ${avg_w:>6.2f} | ${avg_l:>7.2f} | {sl_pct:>8.1f}%")

print(f"\n{'-'*85}")
print("BREAKDOWN BY 3-MINUTE CANDLE PHASE")
print(f"{'-'*85}")
print(f"{'Phase':<22} | {'Trades':<7} | {'Win%':<7} | {'Net PnL':<11} | {'Avg PnL':<9} | {'ProfitFac':<10} | {'Stop-Loss%':<10}")
print(f"{'-'*85}")

for phase in sorted(timing_intervals.keys()):
    t_list = timing_intervals[phase]
    pnls = [t["pnl"] for t in t_list]
    wins = [p for p in pnls if p > 0.0001]
    losses = [p for p in pnls if p < -0.0001]
    tot = len(pnls)
    wr = (len(wins) / tot * 100) if tot else 0.0
    net = sum(pnls)
    gross_w = sum(wins)
    gross_l = abs(sum(losses))
    pf = (gross_w / gross_l) if gross_l > 0 else 0.0
    avg_p = net / tot if tot else 0.0
    sl_count = sum(1 for t in t_list if "STOP_LOSS" in t["exit_reason"])
    sl_pct = (sl_count / len(t_list) * 100) if t_list else 0.0
    print(f"{phase:<22} | {tot:<7} | {wr:>5.1f}% | ${net:>9.2f} | ${avg_p:>7.2f} | {pf:>10.2f} | {sl_pct:>8.1f}%")

conn.close()
