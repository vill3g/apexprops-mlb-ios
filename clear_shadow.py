import time
import json
from backend.btc.kalshi_trader import kalshi_trader
from backend.btc.shadow_executor import update_shadow_settlements

print("Clearing RL shadow backlog...")
for i in range(70):
    update_shadow_settlements(kalshi_trader)
    time.sleep(1)

with open('backend/data/rl_shadow_trades.json', 'r') as f:
    trades = json.load(f)

settled = [t for t in trades if t.get('status') == 'SETTLED']
wins = [t for t in settled if float(t.get('pnl', 0)) > 0]
pnl = sum(float(t.get('pnl', 0)) for t in settled)

print(f"Total Shadow Trades: {len(trades)}")
print(f"Settled: {len(settled)}")
print(f"Wins: {len(wins)}")
print(f"Win Rate: {len(wins)/len(settled)*100 if settled else 0:.2f}%")
print(f"Net PnL: {pnl:.4f}")
