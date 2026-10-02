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
    win_rate = (wins / len(settled) * 100) if settled else 0.0
    trade_size = data[-1].get("trade_size", 100.0) if data else 100.0
    avg_contracts = sum(t.get('contracts', 1) for t in settled) / max(1, len(settled))
    
    eps = data[-1].get("rl_epsilon", "N/A") if data else "N/A"
    
    print(f"--- RL Shadow Engine Status ---")
    print(f"Configured Trade Size: ${trade_size:.2f} per trade")
    print(f"Avg Contracts/Trade:   {avg_contracts:.1f} contracts")
    print(f"Total Trades:          {len(data)} (Settled: {len(settled)} | Open: {len(open_trades)})")
    print(f"Win/Loss Record:       {wins}W - {losses}L ({win_rate:.2f}% Win Rate)")
    print(f"Total Paper PNL:       ${pnl:,.2f}")
    print(f"Current Exploration:   Epsilon = {eps}")
except Exception as e:
    print(f"Error: {e}")
