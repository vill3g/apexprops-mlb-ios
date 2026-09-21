import os, sys, json
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from backend.btc.auto_executor import get_auto_executor
ex = get_auto_executor("BTC")

history = ex.get_trades_history()

paper_trades = [t for t in history if t.get("mode", "").upper() == "PAPER"]
live_trades = [t for t in history if t.get("mode", "").upper() == "LIVE"]

def get_stats(trades):
    settled = [t for t in trades if t.get("status") == "SETTLED"]
    wins = len([t for t in settled if t.get("result") == "WIN"])
    losses = len([t for t in settled if t.get("result") == "LOSS"])
    win_rate = round(wins / len(settled) * 100, 1) if settled else 0.0
    pnl = round(sum(float(t.get("pnl", 0)) for t in settled), 2)
    return {"total": len(settled), "wins": wins, "losses": losses, "win_rate": win_rate, "pnl": pnl}

print("PAPER STATS:")
print(json.dumps(get_stats(paper_trades), indent=2))
print("LIVE STATS:")
print(json.dumps(get_stats(live_trades), indent=2))
