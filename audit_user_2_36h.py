import sqlite3
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

now = datetime.now(ZoneInfo('America/New_York'))
cutoff = now - timedelta(hours=36)

conn = sqlite3.connect('backend/data/users.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute('SELECT * FROM trades WHERE user_id=2 ORDER BY id DESC LIMIT 60')
rows = [dict(r) for r in c.fetchall()]

trades_36h = []
for r in rows:
    ts_str = str(r.get('timestamp') or '')
    dt = None
    for fmt in ['%Y-%m-%d %I:%M:%S %p ET', '%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%dT%H:%M:%S%z']:
        try:
            dt = datetime.strptime(ts_str, fmt)
            break
        except:
            pass
    if dt:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo('America/New_York'))
        if dt >= cutoff:
            trades_36h.append((dt, r))

print(f"User 2 (IppoLang60) - Trades in the last 36 hours (since {cutoff.strftime('%Y-%m-%d %I:%M %p ET')}): {len(trades_36h)}")
print("-" * 100)
for dt, r in trades_36h:
    pnl = r['pnl']
    contracts = r['count']
    ticker = r['ticker']
    side = r['side']
    entry = r['entry_price']
    exit_p = r['exit_price']
    style = r['trading_style']
    reason = r['reason'].encode('ascii', errors='replace').decode('ascii')
    print(f"{dt.strftime('%b %d %I:%M %p ET')} | {ticker:<32} | {side:<3} | Entry: ${entry:<5} | Exit: ${exit_p:<4} | Cnt: {contracts:<2} | PnL: ${pnl:>6.2f} | {style}")
    print(f"   Reason: {reason}")
