import sys
import json
import logging
logging.basicConfig(level=logging.INFO)

from backend.btc.kalshi_trader import kalshi_trader
from backend.btc.auto_executor import auto_executor

trades = auto_executor.get_trades_history()
open_trades = [t for t in trades if t.get('status') == 'OPEN']

print("=== Local Open Trades ===")
for t in open_trades:
    print(f"ID: {t.get('id')}, Ticker: {t.get('ticker')}, Side: {t.get('side')}, Count: {t.get('count')}")

kalshi_positions = kalshi_trader.get_positions()
print("\n=== Kalshi Positions ===")
if kalshi_positions.get("success"):
    for p in kalshi_positions.get("positions", []):
        if p.get("position_fp") > 0:
            print(f"Ticker: {p.get('ticker')}, Position: {p.get('position_fp')}")
else:
    print("Failed to get positions:", kalshi_positions.get("error"))

