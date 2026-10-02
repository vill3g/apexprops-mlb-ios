import json
from datetime import datetime
from backend.database.models import get_db_connection

c = get_db_connection().cursor()
trades = []
for row in c.execute('SELECT raw_json FROM trades ORDER BY id ASC').fetchall():
    t = json.loads(row[0])
    trades.append(t)

todays_trades = [t for t in trades if '2026-10-01' in str(t.get('timestamp', '')) or '2026-10-01' in str(t.get('settled_at', ''))]

# Find the first time ETH or GOLD was traded today
first_multi_asset_time = None
for t in todays_trades:
    asset = t.get('asset', 'BTC')
    if asset in ['ETH', 'GOLD']:
        first_multi_asset_time = t.get('timestamp') or t.get('settled_at')
        break

if not first_multi_asset_time:
    print("No ETH or GOLD trades found today.")
else:
    print(f"First multi-asset trade time: {first_multi_asset_time}")
    
    # We will just use string comparison for timestamps since ISO formats sort well, 
    # or just slice the list from the index of the first multi-asset trade onwards.
    # Since todays_trades is chronological (ORDER BY id ASC):
    start_idx = todays_trades.index(next(t for t in todays_trades if t.get('timestamp') == first_multi_asset_time or t.get('settled_at') == first_multi_asset_time))
    
    recent_trades = todays_trades[start_idx:]
    
    wins = [t for t in recent_trades if t.get('pnl', 0) > 0]
    losses = [t for t in recent_trades if t.get('pnl', 0) < 0]
    total_pnl = sum(t.get('pnl', 0) for t in recent_trades)
    win_rate = (len(wins) / len(recent_trades) * 100) if recent_trades else 0
    
    print(f'\nTotal Trades Since Multi-Asset Launch: {len(recent_trades)}')
    print(f'Wins: {len(wins)}, Losses: {len(losses)}, Win Rate: {win_rate:.1f}%')
    print(f'Total PnL: ${total_pnl:.2f}')
    
    assets = {}
    strategies = {}
    
    for t in recent_trades:
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
