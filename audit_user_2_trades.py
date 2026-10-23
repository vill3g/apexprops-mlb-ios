import sqlite3
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

now = datetime.now(ZoneInfo("America/New_York"))
cutoff = now - timedelta(hours=24)
print(f"Current Time: {now.strftime('%Y-%m-%d %I:%M:%S %p ET')}")
print(f"24-Hour Cutoff: {cutoff.strftime('%Y-%m-%d %I:%M:%S %p ET')}")

conn = sqlite3.connect('backend/data/users.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("SELECT * FROM trades WHERE user_id=2 ORDER BY id DESC")
rows = [dict(r) for r in c.fetchall()]
print(f"\nTotal historical trades for User 2 (IppoLang60): {len(rows)}")

recent_trades = []
for r in rows:
    ts_str = str(r.get('timestamp') or '')
    trade_dt = None
    try:
        # Check standard formats
        for fmt in ["%Y-%m-%d %I:%M:%S %p ET", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S%z"]:
            try:
                trade_dt = datetime.strptime(ts_str.replace(" ET", ""), fmt.replace(" ET", ""))
                trade_dt = trade_dt.replace(tzinfo=ZoneInfo("America/New_York"))
                break
            except:
                pass
    except Exception as e:
        pass
    
    # If float timestamp
    if not trade_dt:
        try:
            val = float(ts_str)
            trade_dt = datetime.fromtimestamp(val, tz=ZoneInfo("America/New_York"))
        except:
            pass

    if trade_dt and trade_dt >= cutoff:
        recent_trades.append((trade_dt, r))

print(f"Trades in the last 24 hours: {len(recent_trades)}")

if recent_trades:
    print("\n--- TRADES IN LAST 24 HOURS ---")
    for dt, r in recent_trades:
        line = f"ID: {r['id']} | Time: {dt.strftime('%Y-%m-%d %I:%M:%S %p ET')} | Ticker: {r['ticker']} | Side: {r['side']} | Mode: {r['mode']} | Status: {r['status']} | Count: {r['count']} | Entry: {r['entry_price']} | Exit: {r['exit_price']} | PnL: ${r['pnl']} | Style: {r['trading_style']} | Reason: {r['reason']} | ExitReason: {r['exit_reason']}"
        print(line.encode('ascii', errors='replace').decode('ascii'))
else:
    print("\nNo trades placed in the last 24 hours. Showing 10 most recent trades regardless of time:")
    for r in rows[:10]:
        line = f"ID: {r['id']} | Time: {r.get('timestamp')} | Ticker: {r['ticker']} | Side: {r['side']} | Mode: {r['mode']} | Status: {r['status']} | Count: {r['count']} | Entry: {r['entry_price']} | Exit: {r['exit_price']} | PnL: ${r['pnl']} | Style: {r['trading_style']} | Reason: {r['reason']} | ExitReason: {r['exit_reason']}"
        print(line.encode('ascii', errors='replace').decode('ascii'))
