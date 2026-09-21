import os, sys, json
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from backend.btc.auto_executor import get_auto_executor
ex = get_auto_executor("BTC")
status = ex.get_status()

print(json.dumps({
    "balance_dollars": status.get("balance_dollars"),
    "total_trades": status.get("total_trades"),
    "wins": status.get("wins"),
    "losses": status.get("losses"),
    "win_rate_pct": status.get("win_rate_pct"),
    "total_pnl_dollars": status.get("total_pnl_dollars"),
    "today_trade_count": status.get("today_trade_count"),
    "today_realized_pnl": status.get("today_realized_pnl"),
    "open_trades_count": status.get("open_trades_count"),
    "mode": status.get("mode")
}, indent=2))
