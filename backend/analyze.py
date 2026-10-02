import sqlite3
import json

conn = sqlite3.connect('C:/Users/Vill3/Desktop/kalshi-ai-trader/backend/data/trades.db')
cursor = conn.cursor()

cursor.execute('SELECT raw_json FROM trades WHERE status IN ("CLOSED", "SETTLED", "closed", "settled")')
rows = cursor.fetchall()

stats = {}

for raw_json, in rows:
    try:
        data = json.loads(raw_json)
    except Exception as e:
        continue
        
    source = data.get('source') or data.get('signal_source') or data.get('strategy') or data.get('trading_style') or data.get('trade_source') or 'Unknown'
    
    pnl = data.get('pnl') or data.get('realized_pnl') or 0
    try:
        pnl = float(pnl)
    except ValueError:
        pnl = 0
        
    is_profitable = pnl > 0
    
    if source not in stats:
        stats[source] = {'wins': 0, 'total': 0, 'total_pnl': 0.0}
    
    stats[source]['total'] += 1
    stats[source]['total_pnl'] += pnl
    if is_profitable:
        stats[source]['wins'] += 1

print(f"{'Source':<20} | {'Wins':>5} | {'Total':>5} | {'Win Rate':>9} | {'Total PnL'}")
print("-" * 65)

best_win_rate = -1
winner = None

# Filter to sources with at least a few trades? The prompt just says "declare the ultimate winner".
# I'll just find the highest win rate.
for source, data in sorted(stats.items(), key=lambda x: x[1]['wins']/x[1]['total'] if x[1]['total'] > 0 else 0, reverse=True):
    win_rate = data['wins'] / data['total'] if data['total'] > 0 else 0
    print(f"{source:<20} | {data['wins']:>5} | {data['total']:>5} | {win_rate:>8.2%} | {data['total_pnl']:>9.2f}")
    
    if source != 'Unknown': # Exclude Unknown from being the winner unless it's the only one
        if win_rate > best_win_rate:
            best_win_rate = win_rate
            winner = source
        # Tie breaker: more total trades?
        elif win_rate == best_win_rate and winner is not None:
            if data['total'] > stats[winner]['total']:
                winner = source

print("\nUltimate Winner:", winner)
