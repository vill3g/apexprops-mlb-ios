import os, sys, json
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from backend.btc.auto_executor import get_auto_executor
ex = get_auto_executor("BTC")

# Current mode (LIVE)
live_status = ex.get_status()

# Switch to PAPER to get its stats
ex.mode = "PAPER"
paper_status = ex.get_status()

# Revert to LIVE
ex.mode = "LIVE"

print("--- LIVE STATS ---")
print(json.dumps({
    "total_trades": live_status.get("total_trades"),
    "wins": live_status.get("wins"),
    "losses": live_status.get("losses"),
    "win_rate_pct": live_status.get("win_rate_pct"),
    "total_pnl_dollars": live_status.get("total_pnl_dollars"),
    "balance_dollars": live_status.get("balance_dollars")
}, indent=2))

print("\n--- PAPER STATS ---")
print(json.dumps({
    "total_trades": paper_status.get("total_trades"),
    "wins": paper_status.get("wins"),
    "losses": paper_status.get("losses"),
    "win_rate_pct": paper_status.get("win_rate_pct"),
    "total_pnl_dollars": paper_status.get("total_pnl_dollars"),
    "balance_dollars": paper_status.get("balance_dollars")
}, indent=2))
