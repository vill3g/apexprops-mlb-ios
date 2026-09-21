import json
import os

try:
    with open('backend/data/rl_shadow_trades.json', 'r') as f:
        data = json.load(f)
    
    settled = [t for t in data if t.get('status') == 'SETTLED']
    open_trades = [t for t in data if t.get('status') == 'OPEN']
    
    pnl = sum(t.get('pnl', 0) for t in settled)
    wins = sum(1 for t in settled if t.get('pnl', 0) > 0)
    losses = sum(1 for t in settled if t.get('pnl', 0) < 0)
    
    eps = data[-1].get("rl_epsilon", "N/A") if data else "N/A"
    
    print(f"Total Trades: {len(data)}")
    print(f"Settled: {len(settled)} | Open: {len(open_trades)}")
    print(f"Paper PNL: {pnl:.4f}")
    print(f"Wins: {wins} | Losses: {losses}")
    print(f"Current Exploration Epsilon: {eps}")
except Exception as e:
    print(f"Error: {e}")
