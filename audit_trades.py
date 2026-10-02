import json
from backend.database.models import get_db_connection

c = get_db_connection().cursor()
trades = []
for row in c.execute('SELECT raw_json FROM trades ORDER BY id DESC').fetchall():
    t = json.loads(row[0])
    trades.append(t)

todays_trades = [t for t in trades if '2026-10-01' in str(t.get('timestamp', '')) or '2026-10-01' in str(t.get('settled_at', ''))]

wins = [t for t in todays_trades if t.get('pnl', 0) > 0]
losses = [t for t in todays_trades if t.get('pnl', 0) < 0]
total_pnl = sum(t.get('pnl', 0) for t in todays_trades)
win_rate = (len(wins) / len(todays_trades) * 100) if todays_trades else 0

print(f'Total Trades Today: {len(todays_trades)}')
print(f'Wins: {len(wins)}, Losses: {len(losses)}, Win Rate: {win_rate:.1f}%')
print(f'Total PnL: ${total_pnl:.2f}')

assets = {}
strategies = {}

for t in todays_trades:
    asset = t.get('asset') or 'BTC'
    style = t.get('trading_style') or t.get('reason') or 'N/A'
    pnl = t.get('pnl', 0)
    
    if asset not in assets: assets[asset] = {'count': 0, 'pnl': 0, 'wins': 0}
    assets[asset]['count'] += 1
    assets[asset]['pnl'] += pnl
    if pnl > 0: assets[asset]['wins'] += 1

    if style not in strategies: strategies[style] = {'count': 0, 'pnl': 0, 'wins': 0}
    strategies[style]['count'] += 1
    strategies[style]['pnl'] += pnl
    if pnl > 0: strategies[style]['wins'] += 1

print("\n--- Breakdown by Asset ---")
for k, v in assets.items():
    print(f"{k}: {v['count']} trades | PnL: ${v['pnl']:.2f} | Win Rate: {(v['wins']/v['count']*100):.1f}%")

print("\n--- Breakdown by Strategy ---")
for k, v in strategies.items():
    print(f"{k}: {v['count']} trades | PnL: ${v['pnl']:.2f} | Win Rate: {(v['wins']/v['count']*100):.1f}%")
