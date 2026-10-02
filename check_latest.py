import json
from backend.database.models import get_db_connection

c = get_db_connection().cursor()
print("Latest 20 trades in DB:")
for row in c.execute('SELECT raw_json FROM trades ORDER BY id DESC LIMIT 20').fetchall():
    t = json.loads(row[0])
    asset = t.get('asset', 'N/A')
    ticker = t.get('ticker', 'N/A')
    status = t.get('status', 'N/A')
    pnl = t.get('pnl', 0)
    live_pnl = t.get('live_pnl', 0)
    ts = t.get('timestamp') or t.get('settled_at')
    print(f"[{ts}] {asset} | {ticker} | Status: {status} | PnL: {pnl} | Live PnL: {live_pnl}")
