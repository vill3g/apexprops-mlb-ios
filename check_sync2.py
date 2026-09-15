import sys
import json
from backend.btc.kalshi_trader import kalshi_trader

kalshi_positions = kalshi_trader.get_positions()
print(json.dumps(kalshi_positions, indent=2))
