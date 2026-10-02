import json
from backend.database.models import get_db_connection

c = get_db_connection().cursor()
all_trades = []
for row in c.execute('SELECT raw_json FROM trades').fetchall():
    t = json.loads(row[0])
    all_trades.append(t)

def get_ts(t):
    return str(t.get('timestamp') or t.get('settled_at') or '')

all_trades.sort(key=get_ts)

multi_asset_trades = []
first_ma_time = None
first_ma_index = -1

for i, t in enumerate(all_trades):
    tk = t.get('ticker', '')
    if 'KXETH' in tk or 'KXGOLD' in tk:
        multi_asset_trades.append(t)
        if not first_ma_time:
            first_ma_time = get_ts(t)
            first_ma_index = i

if not first_ma_time:
    print("No ETH or GOLD trades found AT ALL.")
else:
    print(f"First multi-asset trade time: {first_ma_time}")
    recent = all_trades[first_ma_index:]
    print(f"Total trades since {first_ma_time}: {len(recent)}")
    
    wins = 0
    losses = 0
    total_pnl = 0
    assets = {'BTC': {'count': 0, 'pnl': 0}, 'ETH': {'count': 0, 'pnl': 0}, 'GOLD': {'count': 0, 'pnl': 0}}
    strategies = {}
    
    for t in recent:
        pnl = t.get('pnl', 0)
        # Check if the trade is open (no pnl yet, use live_pnl)
        if t.get('status', '').upper() == 'OPEN' or t.get('status', '').upper() == 'ACTIVE':
            pass # Open trades don't have settled PnL. But we can look at live_pnl if we want.
            
        tk = t.get('ticker', '')
        asset = 'BTC'
        if 'KXETH' in tk: asset = 'ETH'
        elif 'KXGOLD' in tk: asset = 'GOLD'
        
        assets[asset]['count'] += 1
        assets[asset]['pnl'] += pnl
        
        style = t.get('trading_style', 'N/A')
        if style not in strategies: strategies[style] = {'count': 0, 'pnl': 0, 'wins': 0}
        strategies[style]['count'] += 1
        strategies[style]['pnl'] += pnl
        
        if pnl > 0: 
            wins += 1
            strategies[style]['wins'] += 1
        if pnl < 0: 
            losses += 1
        total_pnl += pnl
        
    win_rate = (wins / (wins+losses) * 100) if (wins+losses) > 0 else 0
    
    print(f"Wins: {wins}, Losses: {losses}, Win Rate: {win_rate:.1f}%")
    print(f"Total PnL (Closed): ${total_pnl:.2f}")
    
    print("\n--- Breakdown by Asset ---")
    for k, v in assets.items():
        if v['count'] > 0:
            print(f"{k}: {v['count']} trades | Settled PnL: ${v['pnl']:.2f}")
            
    print("\n--- Breakdown by Strategy ---")
    for k, v in strategies.items():
        if v['count'] > 0:
            print(f"{k}: {v['count']} trades | Settled PnL: ${v['pnl']:.2f}")
            
    print("\nRecent Multi-Asset Trades:")
    for t in multi_asset_trades[-10:]:
        print(f"{get_ts(t)} | {t.get('ticker')} | {t.get('trading_style')} | Settled PnL: ${t.get('pnl', 0):.2f} | Live PnL: ${t.get('live_pnl', 0):.2f} | Status: {t.get('status')}")
